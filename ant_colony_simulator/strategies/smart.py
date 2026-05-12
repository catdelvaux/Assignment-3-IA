from environment import TerrainType, AntPerception
from ant import AntAction, AntStrategy
from common import Direction

import random
import math


# Steps a food broadcast stays active before expiring
BROADCAST_TTL = 40

#Recruit ants witin this many cells of the broadcast food position.
RECRUIT_RADIUS = 20

# Number of steps the ants are obliged to follow a certain direction.
# By sending them in different directions at the beginning will help me have more coverage.
SCOUT_STEPS = 200


class SmartStrategy(AntStrategy):

    def __init__(self):
        """Initialize the strategy with last action tracking"""
        self.memory = {}

        #Shared broadcast table: {food_pos: ttl_remaining}
        self.broadcast: dict[tuple, int] = {}

        #Counter used to assign scout directions in round-robin
        self._next_scout_dir = 0


    # Send ants in evenly spaced directions based on total ant count.
    # Returns an exact angle in degrees so ants truly spread across the map.
    def _assign_scout_dir(self) -> int:
        d = self._next_scout_dir % 8
        self._next_scout_dir += 1
        return d


    #Tells other ants that a food has been found at a certain position
    def _publish_food(self, pos: tuple) -> None:
        self.broadcast[pos] = BROADCAST_TTL


    #This removes expired broadcasts and decrement all remaining TTLs by one
    def _tick_broadcasts(self) -> None:
        """Decrement TTLs and remove expired entries."""
        expired = [p for p, ttl in self.broadcast.items() if ttl <= 0]
        for p in expired:
            del self.broadcast[p]
        for p in self.broadcast:
            self.broadcast[p] -= 1

    #Will recruit other ants when a food is found.
    def _nearby_broadcasts(self, mem: dict) -> list:
        ax, ay = mem["x"], mem["y"]
        return [
            pos for pos in self.broadcast
            if pos not in mem["known_food"]
            and math.hypot(pos[0] - ax, pos[1] - ay) <= RECRUIT_RADIUS
        ]


    def decide_action(self, perception: AntPerception) -> AntAction:
        """Decide an action based on current perception"""
        ant_id = perception.ant_id
        if ant_id not in self.memory:
            self.memory[ant_id] = {
                "x": 0,
                "y": 0,
                "last_action": None,
                "last_direction": perception.direction,
                "known_food": set(),
                "visited": set(),
                "blocked": set(),
                "step": 0,
                "stuck_turns": 0,
                # Assigned at first call — direction spread evenly across all ants
                # Use ant_id as a proxy for total count (ids are sequential from 1)
                "scout_dir": self._assign_scout_dir(),
            }

        mem = self.memory[ant_id]
        mem["step"] += 1

        # Tick shared broadcasts once per ant per step
        self._tick_broadcasts()

        if mem["last_action"] == AntAction.MOVE_FORWARD:
            dx, dy = Direction.get_delta(mem["last_direction"])
            mem["x"] += dx
            mem["y"] += dy
            mem["stuck_turns"] = 0
        elif mem["last_action"] in (AntAction.TURN_LEFT, AntAction.TURN_RIGHT):
            mem["stuck_turns"] += 1
        else:
            mem["stuck_turns"] = 0

        #Go to origin after dropping food at colony
        if (mem["last_action"] == AntAction.DROP_FOOD
                and perception.visible_cells.get((0, 0)) == TerrainType.COLONY):
            mem["x"] = 0
            mem["y"] = 0

        mem["last_direction"] = perception.direction
        mem["visited"].add((mem["x"], mem["y"]))

        # Reffresh food/wall knowledge from FOV, this will reduce the ants being "stucked"
        for (dx, dy), terrain in perception.visible_cells.items():
            abs_pos = (mem["x"] + dx, mem["y"] + dy)
            if terrain == TerrainType.FOOD:
                mem["known_food"].add(abs_pos)
            elif abs_pos in mem["known_food"]:
                mem["known_food"].discard(abs_pos)
            if terrain == TerrainType.WALL:
                mem["blocked"].add(abs_pos)

        # Absobs nearby broadcasts into personal food memory
        if not perception.has_food:
            for pos in self._nearby_broadcasts(mem):
                mem["known_food"].add(pos)

        #Detects when "stucked"
        if mem["stuck_turns"] >= 3:
            return self._commit(mem, perception, self._escape(perception, mem))


        #Pick up food if no food is being carried by the ant
        if (not perception.has_food
                and perception.visible_cells.get((0, 0)) == TerrainType.FOOD):
            food_pos = (mem["x"], mem["y"])
            mem["known_food"].discard(food_pos)
            self._publish_food(food_pos)
            return self._commit(mem, perception, AntAction.PICK_UP_FOOD)

        # On colony carrying food, drop it
        if (perception.has_food
                and perception.visible_cells.get((0, 0)) == TerrainType.COLONY):
            mem["x"] = 0
            mem["y"] = 0
            return self._commit(mem, perception, AntAction.DROP_FOOD)

        # Carrying food, deposit trail then navigate home
        if perception.has_food:
            if mem["step"] % 2 == 0:
                return self._commit(mem, perception, AntAction.DEPOSIT_FOOD_PHEROMONE)

            if perception.can_see_colony():
                col_dir = perception.get_colony_direction()
                if col_dir is not None:
                    return self._commit(
                        mem, perception,
                        self._decide_movement(perception, mem, col_dir)
                    )

            # Dead-reckoned home vector
            home_dir = self._vec_to_dir(-mem["x"], -mem["y"])

            # If straight path home is blocked by a wall, follow home pheromone
            # instead since the trail naturally passes through gaps
            hdx, hdy = Direction.get_delta(Direction(home_dir))
            home_cell = perception.visible_cells.get((hdx, hdy))
            home_blocked = (
                home_cell is None
                or home_cell == TerrainType.WALL
                or (mem["x"] + hdx, mem["y"] + hdy) in mem["blocked"]
            )
            phero_dir = self._strongest_pheromone(perception, use_food=False)

            if home_blocked and phero_dir is not None:
                # Wall ahead: follow home pheromone trail which passes through gaps
                chosen = phero_dir
            elif home_blocked:
                # Wall ahead and no pheromone trail yet: slide along wall toward home
                # Only escape if truly stuck (not just briefly blocked during a turn)
                if mem["stuck_turns"] >= 1:
                    return self._commit(mem, perception, self._escape(perception, mem))
                chosen = home_dir
            else:
                chosen = home_dir

            return self._commit(
                mem, perception, self._decide_movement(perception, mem, chosen)
            )

        #Explore
        # Deposit home pheromone every other step
        if mem["step"] % 2 == 0:
            return self._commit(mem, perception, AntAction.DEPOSIT_HOME_PHEROMONE)

        # SCOUT PHASE: head toward assigned angle.
        # Stop scouting permanently the moment a wall or empty cell is encountered.
        if mem["step"] <= mem.get("scout_steps_override", SCOUT_STEPS):
            target_octant = int((mem["scout_dir"] + 22.5) // 45) % 8
            cdx, cdy = Direction.get_delta(Direction(target_octant))
            cpos = (mem["x"] + cdx, mem["y"] + cdy)
            cell = perception.visible_cells.get((cdx, cdy))
            scout_clear = (
                cell is not None
                and cell != TerrainType.WALL
                and cpos not in mem["blocked"]
            )
            if scout_clear:
                action = self._turn_to(perception.direction, target_octant)
                return self._commit(mem, perception, action)
            else:
                # Hit a wall or empty cell: stop scouting permanently for this ant
                mem["scout_steps_override"] = 0

        #Exploration after scouting (at the beginning)
        # If food is visible, then go there
        if perception.can_see_food():
            fd = perception.get_food_direction()
            if fd is not None:
                return self._commit(
                    mem, perception, self._decide_movement(perception, mem, fd)
                )

        # Go to nearest known food (includes recruited broadcasts)
        target = self._nearest_food(mem)
        if target is not None:
            tdir = self._vec_to_dir(target[0] - mem["x"], target[1] - mem["y"])
            return self._commit(
                mem, perception, self._decide_movement(perception, mem, tdir)
            )

        # Follow food-pheromone gradient as a fallback
        food_dir = self._strongest_pheromone(perception, use_food=True)
        if food_dir is not None and random.random() < 0.70:
            return self._commit(
                mem, perception, self._decide_movement(perception, mem, food_dir)
            )

        #(Purely)Random exploration
        return self._commit(
            mem, perception, self._decide_movement(perception, mem)
        )

    def _decide_movement(self, perception: AntPerception, mem: dict = None,
                         target_dir: int = None) -> AntAction:
        """Decide which direction to move based on current state"""
        if target_dir is not None:
            action = self._turn_to(perception.direction, target_dir)
            if action == AntAction.MOVE_FORWARD and mem is not None:
                fdx, fdy = Direction.get_delta(perception.direction)
                fwd_pos = (mem["x"] + fdx, mem["y"] + fdy)
                fwd_cell = perception.visible_cells.get((fdx, fdy))
                if (fwd_cell is None
                        or fwd_cell == TerrainType.WALL
                        or fwd_pos in mem["blocked"]):
                    return self._escape(perception, mem)
            return action

        if mem is not None:
            fdx, fdy = Direction.get_delta(perception.direction)
            fwd_pos = (mem["x"] + fdx, mem["y"] + fdy)
            fwd_cell = perception.visible_cells.get((fdx, fdy))

            if (fwd_cell is None
                    or fwd_cell == TerrainType.WALL
                    or fwd_pos in mem["blocked"]):
                return self._escape(perception, mem)

            p_fwd = 0.60 if fwd_pos not in mem["visited"] else 0.35
            r = random.random()
            if r < p_fwd:
                return AntAction.MOVE_FORWARD
            elif r < p_fwd + (1 - p_fwd) / 2:
                return AntAction.TURN_LEFT
            else:
                return AntAction.TURN_RIGHT

        return random.choice([AntAction.MOVE_FORWARD, AntAction.TURN_LEFT, AntAction.TURN_RIGHT])

    def _escape(self, perception: AntPerception, mem: dict) -> AntAction:
        """
        Scan all 8 directions and pick the best unblocked one.
        - Carrying food: slide along wall toward home using dot product scoring.
        - Exploring: pick direction with most unvisited cells ahead.
        """
        current = perception.direction
        free_dirs = []

        for d in Direction:
            dx, dy = Direction.get_delta(d)
            neighbour = (mem["x"] + dx, mem["y"] + dy)
            terrain = perception.visible_cells.get((dx, dy))
            if terrain is None or terrain == TerrainType.WALL or neighbour in mem["blocked"]:
                continue
            free_dirs.append(d)

        if not free_dirs:
            return random.choice([AntAction.TURN_LEFT, AntAction.TURN_RIGHT])

        if perception.has_food:
            # Slide along wall toward home.
            # Score each free direction by:
            #   1. Dot product with home vector (progress toward home)
            #   2. Bonus if the cells ahead are not visited (likely a gap)
            home_dir = self._vec_to_dir(-mem["x"], -mem["y"])
            hdx, hdy = Direction.get_delta(Direction(home_dir))

            def home_slide_score(d):
                ddx, ddy = Direction.get_delta(d)
                # Base: progress toward home
                dot = ddx * hdx + ddy * hdy
                # Bonus: unvisited cells ahead suggest a gap or new passage
                gap_bonus = 0
                for step in range(1, 4):
                    npos = (mem["x"] + ddx * step, mem["y"] + ddy * step)
                    if npos not in mem["visited"]:
                        gap_bonus += 1
                return dot + gap_bonus * 0.5

            best = max(free_dirs, key=home_slide_score)
        else:
            # Exploring: steer toward most unvisited territory
            def unvisited_score(d):
                ddx, ddy = Direction.get_delta(d)
                score = 0
                for step in range(1, 4):
                    npos = (mem["x"] + ddx * step, mem["y"] + ddy * step)
                    if npos not in mem["visited"]:
                        score += 1
                return score

            best = max(free_dirs, key=unvisited_score)

        return self._turn_to(current, best.value)

    @staticmethod
    def _turn_to(current_direction: Direction, target_dir: int) -> AntAction:
        if current_direction.value == target_dir:
            return AntAction.MOVE_FORWARD
        diff = (target_dir - current_direction.value) % 8
        return AntAction.TURN_RIGHT if diff <= 4 else AntAction.TURN_LEFT

    #Convert a displacement vector to the nearest Direction value (0-7)
    @staticmethod
    def _vec_to_dir(dx: float, dy: float) -> int:

        if dx == 0 and dy == 0:
            return Direction.NORTH.value
        angle = (math.degrees(math.atan2(dy, dx)) + 90) % 360
        return int((angle + 22.5) // 45) % 8

    #Return the Direction value of the strongest pheromone gradient, or None
    @staticmethod
    def _strongest_pheromone(perception: AntPerception, use_food: bool):
        src = perception.food_pheromone if use_food else perception.home_pheromone
        bucket: dict[int, float] = {}
        for (dx, dy), val in src.items():
            if val <= 0:
                continue
            dist = math.hypot(dx, dy) or 1.0
            angle = (math.degrees(math.atan2(dy, dx)) + 90) % 360
            d = int((angle + 22.5) // 45) % 8
            bucket[d] = bucket.get(d, 0.0) + val / dist
        return max(bucket, key=bucket.get) if bucket else None

    #Return the closest remembered food position, None of no more.
    @staticmethod
    def _nearest_food(mem: dict):
        if not mem["known_food"]:
            return None
        ax, ay = mem["x"], mem["y"]
        return min(mem["known_food"],
                   key=lambda p: (p[0] - ax) ** 2 + (p[1] - ay) ** 2)

    @staticmethod
    def _commit(mem: dict, perception: AntPerception, action: AntAction) -> AntAction:
        mem["last_action"] = action
        mem["last_direction"] = perception.direction
        return action