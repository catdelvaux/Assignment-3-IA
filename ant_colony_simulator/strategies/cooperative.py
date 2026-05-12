from environment import TerrainType, AntPerception, Direction
from ant import AntAction, AntStrategy

import random

class CooperativeStrategy(AntStrategy):
    """
    # TODO: Insert your code here
    """

    def __init__(self):
        """Initialize the strategy with last action tracking"""
        self.last_action = {}

    def turn_to(self, current_direction, target_direction):
        if current_direction.value == target_direction:
            return AntAction.MOVE_FORWARD

        diff = (target_direction - current_direction.value) % 8

        if diff <= 4:
            return AntAction.TURN_RIGHT
        else:
            return AntAction.TURN_LEFT
        
    def follow_pheromone(self, pheromones):
        best_direction = None
        best_value = 0

        for (dx, dy), value in pheromones.items():
            if value > best_value:
                best_value = value
                best_direction = self.direction_to_target(dx, dy)

        return best_direction
        
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


    def decide_action(self, perception: AntPerception) -> AntAction:
        """Decide an action based on current perception"""

        ant_id = perception.ant_id

        if ant_id not in self.last_action:
            self.last_action[ant_id] = None

        # if carrying food and on colony: drop it
        if perception.has_food and perception.visible_cells.get((0, 0)) == TerrainType.COLONY:
            action = AntAction.DROP_FOOD
            self.last_action[ant_id] = action
            return action

        # if not carrying food and on food: pick it up
        if not perception.has_food and perception.visible_cells.get((0, 0)) == TerrainType.FOOD:
            action = AntAction.PICK_UP_FOOD
            self.last_action[ant_id] = action
            return action

        # if carrying food: leave food pheromone, then try to go home
        if perception.has_food:

            # deposit one turn, move the next turn
            if self.last_action[ant_id] != AntAction.DEPOSIT_FOOD_PHEROMONE: #alternate between depositing and moving to not waste steps standing still
                action = AntAction.DEPOSIT_FOOD_PHEROMONE
                self.last_action[ant_id] = action
                return action

            if perception.can_see_colony():
                colony_direction = perception.get_colony_direction()
                if colony_direction is not None:
                    action = self.turn_to(perception.direction, colony_direction)
                    self.last_action[ant_id] = action
                    return action

            home_direction = self.follow_pheromone(perception.home_pheromone)
            if home_direction is not None:
                action = self.turn_to(perception.direction, home_direction)
                self.last_action[ant_id] = action
                return action

            action = self._decide_movement(perception)
            self.last_action[ant_id] = action
            return action

        # if not carrying food: leave home pheromone, then search food
        if self.last_action[ant_id] != AntAction.DEPOSIT_HOME_PHEROMONE:
            action = AntAction.DEPOSIT_HOME_PHEROMONE
            self.last_action[ant_id] = action
            return action

        if perception.can_see_food():
            food_direction = perception.get_food_direction()
            if food_direction is not None:
                action = self.turn_to(perception.direction, food_direction)
                self.last_action[ant_id] = action
                return action

        food_pheromone_direction = self.follow_pheromone(perception.food_pheromone)
        if food_pheromone_direction is not None:
            action = self.turn_to(perception.direction, food_pheromone_direction)
            self.last_action[ant_id] = action
            return action

        action = self._decide_movement(perception)
        self.last_action[ant_id] = action
        return action

    def _decide_movement(self, perception: AntPerception) -> AntAction:
        """Decide which direction to move based on current state"""
        r = random.random()

        if r < 0.85: #85% forward to keep moving, small chance to turn to avoid getting stuck, going too straight risks missing food nearby
            return AntAction.MOVE_FORWARD
        elif r < 0.925:
            return AntAction.TURN_LEFT
        else:
            return AntAction.TURN_RIGHT