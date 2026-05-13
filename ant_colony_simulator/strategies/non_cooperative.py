from environment import TerrainType, AntPerception, Direction
from ant import AntAction, AntStrategy

import random


class NonCooperativeStrategy(AntStrategy):
    """
    # TODO: Insert your code here
    """

    def __init__(self):
        """Initialize the strategy with last action tracking"""
        self.memory = {}

    def turn_to(self, current_direction, target_direction):
        if current_direction.value == target_direction:
            return AntAction.MOVE_FORWARD

        diff = (target_direction - current_direction.value) % 8

        if diff <= 4:
            return AntAction.TURN_RIGHT
        else:
            return AntAction.TURN_LEFT
        
    def direction_to_home(self, x, y):
        dx = -x
        dy = -y

        if dx == 0 and dy < 0:
            return Direction.NORTH.value
        elif dx > 0 and dy < 0:
            return Direction.NORTHEAST.value
        elif dx > 0 and dy == 0:
            return Direction.EAST.value
        elif dx > 0 and dy > 0:
            return Direction.SOUTHEAST.value
        elif dx == 0 and dy > 0:
            return Direction.SOUTH.value
        elif dx < 0 and dy > 0:
            return Direction.SOUTHWEST.value
        elif dx < 0 and dy == 0:
            return Direction.WEST.value
        elif dx < 0 and dy < 0:
            return Direction.NORTHWEST.value

        return Direction.NORTH.value
    
    def direction_to_target(self, dx, dy):
        if dx == 0 and dy < 0:
            return Direction.NORTH.value
        elif dx > 0 and dy < 0:
            return Direction.NORTHEAST.value
        elif dx > 0 and dy == 0:
            return Direction.EAST.value
        elif dx > 0 and dy > 0:
            return Direction.SOUTHEAST.value
        elif dx == 0 and dy > 0:
            return Direction.SOUTH.value
        elif dx < 0 and dy > 0:
            return Direction.SOUTHWEST.value
        elif dx < 0 and dy == 0:
            return Direction.WEST.value
        elif dx < 0 and dy < 0:
            return Direction.NORTHWEST.value
        return Direction.NORTH.value
    
    def opposite_direction(self, direction):
       return Direction((direction.value + 4) % 8).value

        
    def decide_action(self, perception: AntPerception) -> AntAction:
        """Decide an action based on current perception"""

        ant_id = perception.ant_id
 
        # initialize memory for this ant if first time we see it
        if ant_id not in self.memory:
            self.memory[ant_id] = {
                "x": 0,
                "y": 0,
                "last_action": None,
                "last_direction": perception.direction,
                "known_food": [],
                "path": [],
                "visited": set(),
                "blocked": set()
            }
 
        memory = self.memory[ant_id]
 
        # update position only if last action was move forward, also check we didn't hit a wall
        if memory["last_action"] == AntAction.MOVE_FORWARD:
            dx, dy = Direction.get_delta(memory["last_direction"])
            next_position = (memory["x"] + dx, memory["y"] + dy)
 
            if perception.visible_cells.get((0, 0)) != TerrainType.WALL:
                memory["x"] += dx
                memory["y"] += dy
 
                # only save path steps while exploring,not while carrying food
                if not perception.has_food:
                    memory["path"].append(memory["last_direction"])
            else:
                memory["blocked"].add(next_position)
 
        memory["last_direction"] = perception.direction
        memory["visited"].add((memory["x"], memory["y"]))
 
        # save food positions seen by this ant
        for (dx, dy), cell_type in perception.visible_cells.items():
            if cell_type == TerrainType.FOOD:
                food_position = (memory["x"] + dx, memory["y"] + dy)
                if food_position not in memory["known_food"]:
                    memory["known_food"].append(food_position)
 
        # if has food and is on colony, drop it
        if perception.has_food:
            if perception.visible_cells.get((0, 0)) == TerrainType.COLONY:
                memory["x"] = 0
                memory["y"] = 0
                memory["path"] = []
                action = AntAction.DROP_FOOD
                memory["last_action"] = action
                return action
 
        # if no food and on food cell, pick it up
        if not perception.has_food:
            if perception.visible_cells.get((0, 0)) == TerrainType.FOOD:
                action = AntAction.PICK_UP_FOOD
                memory["last_action"] = action
                return action
 
        # if has food and sees colony, go toward it
        if perception.has_food and perception.can_see_colony():
            colony_direction = perception.get_colony_direction()
            if colony_direction is not None:
                action = self.turn_to(perception.direction, colony_direction)
                memory["last_action"] = action
                return action
 
        # if has food, retrace path back home step by step, pop() only when actually moving forward to avoid skipping steps
        if perception.has_food and memory["path"]:
            last_direction = memory["path"][-1]
            target_direction = self.opposite_direction(last_direction)
 
            action = self.turn_to(perception.direction, target_direction)
 
            if action == AntAction.MOVE_FORWARD:
                memory["path"].pop()
 
            memory["last_action"] = action
            return action
 
        # if path is empty, use approximate home direction from position
        if perception.has_food:
            target_direction = self.direction_to_home(memory["x"], memory["y"])
            action = self.turn_to(perception.direction, target_direction)
            memory["last_action"] = action
            return action
 
        # if no food and sees food,go toward visible food
        if not perception.has_food and perception.can_see_food():
            food_direction = perception.get_food_direction()
            if food_direction is not None:
                action = self.turn_to(perception.direction, food_direction)
                memory["last_action"] = action
                return action
            
        # if no food but remembers food location,go there directly
        if not perception.has_food and memory["known_food"]:
            food_x, food_y = memory["known_food"][0]
 
            dx = food_x - memory["x"]
            dy = food_y - memory["y"]
 
            target_direction = self.direction_to_target(dx, dy)
            action = self.turn_to(perception.direction, target_direction)
            memory["last_action"] = action
            return action
 
        #explore randomly
        action = self._decide_movement(perception)
        memory["last_action"] = action
        return action
    
    def _decide_movement(self, perception: AntPerception) -> AntAction:
        """Decide which direction to move based on current state"""
        ant_id = perception.ant_id
        memory = self.memory[ant_id]

        current_direction = perception.direction
        forward_dx, forward_dy = Direction.get_delta(current_direction)
        forward_position = (memory["x"] + forward_dx, memory["y"] + forward_dy)

        # if the cell in front is known as blocked, turn instead of moving
        if forward_position in memory["blocked"]:
            return random.choice([AntAction.TURN_LEFT, AntAction.TURN_RIGHT])

        # avoid going too often to already visited positions
        if forward_position in memory["visited"]:
            r = random.random()
            if r < 0.45:
                return AntAction.MOVE_FORWARD
            elif r < 0.725:
                return AntAction.TURN_LEFT
            else:
                return AntAction.TURN_RIGHT

        # if forward position seems new, prefer moving forward
        r = random.random()
        if r < 0.8:
            return AntAction.MOVE_FORWARD
        elif r < 0.9:
            return AntAction.TURN_LEFT
        else:
            return AntAction.TURN_RIGHT