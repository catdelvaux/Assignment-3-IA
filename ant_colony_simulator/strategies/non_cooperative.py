from environment import TerrainType, AntPerception, Direction
from ant import AntAction, AntStrategy

import random


class NonCooperativeStrategy(AntStrategy):
    """
    # TODO: Insert your code here
    """

    def __init__(self):
        """Initialize the strategy with last action tracking"""
        # TODO: Insert your code here
        self.memory = {}

    def turn_to(self, current_direction, target_direction):
        if current_direction.value == target_direction:
            return AntAction.MOVE_FORWARD

        diff = (target_direction - current_direction.value) % 8

        if diff <= 4:
            return AntAction.TURN_RIGHT
        else:
            return AntAction.TURN_LEFT
        
    def _direction_to_home(self, x, y):
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
    
    def _direction_to_target(self, dx, dy):
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

        
    def decide_action(self, perception: AntPerception) -> AntAction:
        """Decide an action based on current perception"""

        # TODO: Insert your code here
        ant_id = perception.ant_id

        if ant_id not in self.memory:
            self.memory[ant_id] = {
                "x": 0,
                "y": 0,
                "last_action": None,
                "last_direction": perception.direction,
                "known_food": []
            }

        mem = self.memory[ant_id]

        if mem["last_action"] == AntAction.MOVE_FORWARD:
            dx, dy = Direction.get_delta(mem["last_direction"])
            mem["x"] += dx
            mem["y"] += dy

        mem["last_direction"] = perception.direction

        # Save food positions seen by this ant
        for (dx, dy), cell_type in perception.visible_cells.items():
            if cell_type == TerrainType.FOOD:
                food_pos = (mem["x"] + dx, mem["y"] + dy)
                if food_pos not in mem["known_food"]:
                    mem["known_food"].append(food_pos)

        # if has food and is on colony
        if perception.has_food:
            if perception.visible_cells.get((0, 0)) == TerrainType.COLONY:
                mem["x"] = 0
                mem["y"] = 0
                action = AntAction.DROP_FOOD
                mem["last_action"] = action
                return action

        # if no food and sees food, go toward visible food
        if not perception.has_food:
            if perception.visible_cells.get((0, 0)) == TerrainType.FOOD:
                current_pos = (mem["x"], mem["y"])
                if current_pos in mem["known_food"]:
                    mem["known_food"].remove(current_pos)

                action = AntAction.PICK_UP_FOOD
                mem["last_action"] = action
                return action

        # if has food and sees colony, go toward visible colony
        if perception.has_food and perception.can_see_colony():
            colony_direction = perception.get_colony_direction()
            if colony_direction is not None:
                action = self.turn_to(perception.direction, colony_direction)
                mem["last_action"] = action
                return action

        # if has food, go back home using memory
        if perception.has_food:
            target_direction = self._direction_to_home(mem["x"], mem["y"])
            action = self.turn_to(perception.direction, target_direction)
            mem["last_action"] = action
            return action
        
        # if no food and sees food, go toward visible food
        if not perception.has_food and perception.can_see_food():
            food_direction = perception.get_food_direction()
            if food_direction is not None:
                action = self.turn_to(perception.direction, food_direction)
                mem["last_action"] = action
                return action
            
        # if no food but remembers food, go toward remembered food
        if not perception.has_food and mem["known_food"]:
            food_x, food_y = mem["known_food"][0]

            dx = food_x - mem["x"]
            dy = food_y - mem["y"]

            target_direction = self._direction_to_target(dx, dy)
            action = self.turn_to(perception.direction, target_direction)
            mem["last_action"] = action
            return action

        # explore randomly
        action = self._decide_movement(perception)
        mem["last_action"] = action
        return action
    
    def _decide_movement(self, perception: AntPerception) -> AntAction:
        """Decide which direction to move based on current state"""
        # TODO: Insert your code here
        r = random.random()

        if perception.has_food: #if ant has food, try to go home
            if r < 0.85:
                return AntAction.MOVE_FORWARD
            elif r < 0.925:
                return AntAction.TURN_LEFT
            else:
                return AntAction.TURN_RIGHT

        else: #keep exploring
            if r < 0.7:
                return AntAction.MOVE_FORWARD
            elif r < 0.85:
                return AntAction.TURN_LEFT
            else:
                return AntAction.TURN_RIGHT
        