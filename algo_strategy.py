import gamelib
import random
import math
import warnings
from sys import maxsize
import json

"""
Most of the algo code you write will be in this file unless you create new
modules yourself. Start by modifying the 'on_turn' function.

Advanced strategy tips: 

  - You can analyze action frames by modifying on_action_frame function

  - The GameState.map object can be manually manipulated to create hypothetical 
  board states. Though, we recommended making a copy of the map to preserve 
  the actual current map state.
"""


class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))
        global enemy_health, my_health, enemy_max_MP, flag
        enemy_health = [30]
        my_health = 30
        enemy_max_MP = 0
        flag = False

    def on_game_start(self, config):
        """ 
        Read in config and perform any initial setup here 
        """
        gamelib.debug_write('Configuring your custom algo strategy...')
        self.config = config
        global WALL, SUPPORT, TURRET, SCOUT, DEMOLISHER, INTERCEPTOR, MP, SP
        WALL = config["unitInformation"][0]["shorthand"]
        SUPPORT = config["unitInformation"][1]["shorthand"]
        TURRET = config["unitInformation"][2]["shorthand"]
        SCOUT = config["unitInformation"][3]["shorthand"]
        DEMOLISHER = config["unitInformation"][4]["shorthand"]
        INTERCEPTOR = config["unitInformation"][5]["shorthand"]
        MP = 1
        SP = 0
        # This is a good place to do initial setup
        self.scored_on_locations = []

    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
        global enemy_health, my_health, enemy_max_MP
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(game_state.turn_number))
        game_state.suppress_warnings(True)  # Comment or remove this line to enable warnings.
        enemy_max_MP = max(game_state.get_resource(MP, 1), enemy_max_MP)
        self.starter_strategy(game_state)
        my_health = game_state.my_health
        enemy_health.append(game_state.enemy_health)
        game_state.submit_turn()

    """
    NOTE: All the methods after this point are part of the sample starter-algo
    strategy and can safely be replaced for your custom algo.
    """

    def has_path_to_edge(self, game_state, start_loc):
        edges = set([*[tuple(i) for i in game_state.game_map.get_edges()[0]],
                     *[tuple(i) for i in game_state.game_map.get_edges()[1]]])
        avail_locs = [start_loc]
        seen_locs = set([tuple(start_loc)])
        while avail_locs:
            old_loc = avail_locs.pop(0)
            x, y = old_loc
            new_locs = [(x, y + 1), (x, y - 1), (x + 1, y), (x - 1, y)]
            for loc in new_locs:
                if not game_state.game_map.in_arena_bounds(loc):
                    continue
                if len(game_state.game_map[loc]) > 0:
                    continue
                if loc in edges:
                    return True
                if loc in seen_locs:
                    continue
                avail_locs.append(loc)
                seen_locs.add(loc)

        return False

    def starter_strategy(self, game_state):
        """
        For defense we will use a spread out layout and some interceptors early on.
        We will place turrets near locations the opponent managed to score on.
        For offense we will use long range demolishers if they place stationary units near the enemy's front.
        If there are no stationary units to attack in the front, we will send Scouts to try and score quickly.
        """
        # First, place basic defenses
        global enemy_health, my_health, enemy_max_MP, flag

        # debug
        gamelib.debug_write(len(game_state.game_map[0, 14]))

        if game_state.turn_number > 1 and self.detect_enemy_unit(game_state, unit_type=[TURRET, WALL, SUPPORT],
                                                                 valid_y=[14, 15, 16, 17]) <= 3:
            game_state.attempt_spawn(SUPPORT, [[15, 4]])
            game_state.attempt_spawn(INTERCEPTOR, [16, 2], 1)
            game_state.attempt_spawn(SCOUT, [4, 9], 1000)
            return

        if game_state.turn_number >= 3:
            self.generate_bait(game_state)

        # flag = self.move_to_another_path(game_state, flag)
        self.build_reactive_defense(game_state)
        self.build_defences(game_state)
        # Now build reactive defenses based on where the enemy scored

        has_path = self.has_path_to_edge(game_state, [14, 13])

        tol = 16
        if game_state.my_health < my_health:
            tol = min(tol, enemy_max_MP - 0.99)
        if game_state.get_resource(MP, player_index=1) >= tol:
            if has_path:
                game_state.attempt_spawn(INTERCEPTOR, [17, 3], 1)
        if game_state.turn_number <= 1:
            if has_path:
                game_state.attempt_spawn(SCOUT, [5, 8], 4)
                game_state.attempt_spawn(SCOUT, [4, 9], 1000)
            return

        scout_spawn_location_options = [[5, 8], [4, 9], [14, 0]]
        best_location = self.least_damage_spawn_location(game_state, scout_spawn_location_options)
        if best_location[0] < 25:
            if has_path:
                if game_state.get_resource(MP) >= 16 * game_state.type_cost(SCOUT)[MP]:
                    game_state.attempt_spawn(SCOUT, best_location[1], 5)
                    game_state.attempt_spawn(SCOUT, [4, 9], 1000)

        # elif flag:
        #     if game_state.get_resource(MP) >= 11 * game_state.type_cost(SCOUT)[MP]:
        #         game_state.attempt_spawn(SCOUT, [4, 9], 1000)
        elif (self.detect_enemy_unit(game_state, unit_type=[TURRET, WALL, SUPPORT],
                                     valid_x=[20, 21, 22, 23, 24, 25, 26, 27], valid_y=[14]) >= 7):
            if game_state.get_resource(MP) >= 7 * game_state.type_cost(DEMOLISHER)[MP] + 1:
                if has_path:
                    game_state.attempt_spawn(INTERCEPTOR, [16, 2], 1)
                else:
                    game_state.attempt_spawn(DEMOLISHER, [4, 9], 7)
                    game_state.attempt_spawn(SCOUT, [4, 9], 1000)

            else:
                return
        else:
            if len(enemy_health) >= 10:
                if len(set(enemy_health[len(enemy_health) - 7:])) <= 1:
                    if len(enemy_health) >= 20 and len(set(enemy_health[len(enemy_health) - 17:])) <= 1:
                        if game_state.get_resource(MP) >= 7 * game_state.type_cost(DEMOLISHER)[MP] + 1:
                            if has_path:
                                game_state.attempt_spawn(INTERCEPTOR, [16, 2], 1)
                            game_state.attempt_spawn(DEMOLISHER, [4, 9], 100)
                        if game_state.get_resource(MP, player_index=1) >= tol:
                            if has_path:
                                game_state.attempt_spawn(INTERCEPTOR, [17, 3], 1)
                        return

        if game_state.get_resource(MP) >= 16 * game_state.type_cost(SCOUT)[MP]:
            # game_state.attempt_spawn(DEMOLISHER, best_location[1], 2)
            game_state.attempt_spawn(SCOUT, [5, 8], 10)
            game_state.attempt_spawn(SCOUT, [4, 9], 1000)

        # # If the turn is less than 5, stall with interceptors and wait to see enemy's base
        # if game_state.turn_number < 26:
        #     game_state.attempt_spawn(DEMOLISHER, [4,9], 1000)
        #     game_state.attempt_spawn(SCOUT, [4,9], 1000)
        #     # self.stall_defensive_interceptors(game_state)
        # else:
        #     # Now let's analyze the enemy base to see where their defenses are concentrated.
        #     # If they have many units in the front we can build a line for our demolishers to attack them at long range.
        #     if self.detect_enemy_unit(game_state, unit_type=None, valid_x=list(range(28)), valid_y=[15]) > 15 or self.detect_enemy_unit(game_state, unit_type=None, valid_x=list(range(1,27)), valid_y=[14])>13:
        #         self.demolisher_line_strategy(game_state)
        #     else:
        #         if game_state.turn_number % 2 == 0:
        #             game_state.attempt_spawn(DEMOLISHER, [4, 9], 1000)
        #             game_state.attempt_spawn(SCOUT, [4, 9], 1000)
        # scout_spawn_location_options = [[14, 0]]
        # game_state.attempt_spawn(SCOUT, scout_spawn_location_options, 1000)
        # #如果有三回合没有造成伤害了，那就派出demolisher
        # if game_state.turn_number % 1 == 0:
        #     # To simplify we will just check sending them from back left and right
        #     # scout_spawn_location_options = [[13, 0], [14, 0]]
        #     # best_location = self.least_damage_spawn_location(game_state, scout_spawn_location_options)
        #     # game_state.attempt_spawn(SCOUT, best_location, 1000)
        #     scout_spawn_location_options = [[14, 0]]
        #     game_state.attempt_spawn(SCOUT, scout_spawn_location_options, 1000)
        #
        # # Lastly, if we have spare SP, let's build some supports
        # support_locations = [[8, 10], [13, 5], [12, 6], [10, 10], [13, 11], [15, 6], [12, 5], [11, 6]]
        # game_state.attempt_spawn(SUPPORT, support_locations)
        # game_state.attempt_upgrade(support_locations)

    def move_to_another_path(self, game_state, flag):
        if flag == True:
            turret_list = [[22, 13], [24, 13], [25, 13], [21, 12], [22, 12], [23, 12], [24, 12], [21, 11], [22, 11],
                           [21, 10], [22, 10]]
            game_state.attempt_spawn(TURRET, turret_list)
            return True
        if game_state.turn_number > 24 and len(set(enemy_health[len(enemy_health) - 13:])) <= 1:
            if game_state.get_resource(SP, player_index=0) <= 16:
                return False
            else:
                remove_list = []
                for x in range(22, 28, 1):
                    for y in [11, 12, 13]:
                        remove_list.append([x, y])
                remove_list.append([22, 10])
                remove_list.append([23, 10])
                remove_list.append([22, 9])
                remove_list.append([23, 9])
                game_state.attempt_remove(remove_list)
                return True
        else:
            return False

    def build_defences(self, game_state):
        """
        Build basic defenses using hardcoded locations.
        Remember to defend corners and avoid placing units in the front where enemy demolishers can attack them.
        """
        global enemy_health, my_health
        # Useful tool for setting up your base locations: https://www.kevinbai.design/terminal-map-maker
        # More community tools available at: https://terminal.c1games.com/rules#Download

        wall_locations = [[0, 13], [1, 12], [27, 13]]
        game_state.attempt_spawn(WALL, wall_locations)
        for x in range(2, 6, 1):
            game_state.attempt_spawn(WALL, [x, 11])
        for x in [26, 23]:
            game_state.attempt_spawn(WALL, [x, 12])
        for x in range(6, 9):
            game_state.attempt_spawn(WALL, [x, 16 - x])
        for x in range(9, 18):
            game_state.attempt_spawn(WALL, [x, 8])
        for x in [18, 20]:
            game_state.attempt_spawn(WALL, [x, x - 10])
        wall_locations.append([22, 11])
        wall_locations.append([22, 10])
        game_state.attempt_spawn(WALL, wall_locations)

        turret_locations = [[23, 11], [23, 10], [23, 9], [20, 9], [19, 8], [22, 8], [21, 7], [19, 9], [18, 7]]
        game_state.attempt_spawn(TURRET, turret_locations)

        support_locations = [[4, 10]]
        game_state.attempt_spawn(SUPPORT, support_locations)

        game_state.attempt_spawn(SUPPORT, [5, 10])
        # game_state.attempt_spawn(SUPPORT, [23, 9])
        game_state.attempt_spawn(TURRET, [[20, 6], [19, 5]])

        if game_state.turn_number > 6:
            game_state.attempt_spawn(TURRET, [19, 10])
            game_state.attempt_upgrade([19, 10])
        game_state.attempt_spawn(WALL, [20, 11])
        upgrade_locations = [[20, 9], [23, 11], [0, 13], [27, 13], [1, 12]]
        game_state.attempt_upgrade(upgrade_locations)
        game_state.attempt_spawn(SUPPORT, [6, 9])
        upgrade_locations = [[5, 10], [5, 11], [23, 12], [6, 10]]
        game_state.attempt_upgrade(upgrade_locations)
        game_state.attempt_upgrade(turret_locations)
        for x in range(2, 6, 1):
            upgrade_locations.append([x, 11])
        game_state.attempt_upgrade(upgrade_locations)
        game_state.attempt_upgrade([20, 11])
        game_state.attempt_upgrade([22, 11])
        game_state.attempt_upgrade([22, 10])
        game_state.attempt_upgrade([4, 10])
        game_state.attempt_upgrade([20, 10])

        turret_locations = []

        for x in range(19, 17, -1):
            turret_locations.append([x, x - 11])
            turret_locations.append([x, x - 14])
        game_state.attempt_spawn(TURRET, turret_locations)
        game_state.attempt_spawn(WALL, [22, 9])
        game_state.attempt_spawn(TURRET, [19, 11])
        game_state.attempt_spawn(TURRET, [17, 6])
        game_state.attempt_spawn(SUPPORT, [7, 8])
        support_locations = [[8, 7]]
        game_state.attempt_spawn(SUPPORT, support_locations)

        # game_state.attempt_spawn(WALL, [[3, 12], [4, 12], [26, 13], [25, 13], [24, 13]])
        # game_state.attempt_spawn(TURRET, [[2, 12]])
        # game_state.attempt_upgrade([[2, 12], [4, 12]])

        # if len(enemy_health) >= 10:
        #     if len(set(enemy_health[len(enemy_health)-10:])) <= 1:
        #         game_state.attempt_spawn(WALL, [[20, 12], [20, 11], [21, 13]])
        #         game_state.attempt_upgrade([[20, 12], [20, 11], [21, 13]])
        x = 9
        while game_state.get_resource(SP) >= 16 and x < 17:
            game_state.attempt_spawn(SUPPORT, [x, 7])
            x = x + 1
        i = 0
        upgrade_locations = [[23, 12], [20, 11], [19, 8], [23, 10], [18, 7]]
        while game_state.get_resource(SP) >= 16 and i < len(upgrade_locations):
            game_state.attempt_upgrade(upgrade_locations[i])
            i = i + 1
        x = 9
        while game_state.get_resource(SP) >= 16 and x < 17:
            game_state.attempt_upgrade([x, 7])
            x = x + 1
        if game_state.get_resource(SP) >= 16:
            game_state.attempt_upgrade([21, 7])
        x = 10
        while game_state.get_resource(SP) >= 16 and x <= 15:
            game_state.attempt_spawn(SUPPORT, [x, 4])
            x = x + 1
        x = 10
        while game_state.get_resource(SP) >= 16 and x <= 15:
            game_state.attempt_upgrade([x, 4])
            x = x + 1

    def generate_bait(self, game_state):
        if len(game_state.game_map[1, 15]) == 0:
            # enemy removed left wall
            if len(game_state.game_map[1, 14]) == 0 and len(game_state.game_map[2, 15]) == 0 and len(
                    game_state.game_map[2, 16]) == 0 \
                    and len(game_state.game_map[3, 16]) == 0 and len(game_state.game_map[3, 17]) == 0:
                # enemy may want to attack 
                game_state.attempt_spawn(WALL, [[2, 12], [3, 12]])
        else:
            game_state.attempt_remove([[2, 12], [3, 12]])

        if len(game_state.game_map[26, 15]) == 0:
            # enemy removed right wall
            if len(game_state.game_map[26, 14]) == 0 and len(game_state.game_map[25, 15]) == 0 and len(
                    game_state.game_map[25, 16]) == 0 \
                    and len(game_state.game_map[24, 16]) == 0 and len(game_state.game_map[24, 17]) == 0:
                # enemy may want to attack 
                game_state.attempt_spawn(WALL, [[24, 12], [25, 12]])
        else:
            game_state.attempt_remove([[24, 12], [25, 12]])

        # if len(game_state.game_map[1,15]) > 0: 
        #     self.enemy_left_wall = True
        # else: 
        #     self.enemy_left_wall = False

        # if len(game_state.game_map[27,14]) > 0: 
        #     self.enemy_right_wall = True
        # else: 
        #     self.enemy_right_wall = False

    def build_reactive_defense(self, game_state):
        """
        This function builds reactive defenses based on where the enemy scored on us from.
        We can track where the opponent scored by looking at events in action frames 
        as shown in the on_action_frame function
        """
        global enemy_health, my_health, flag_remove
        # upgrade_locations = [[27, 13], [0, 13]]
        upgrade_locations = [[27, 13], [0, 13], [1, 12], [2, 11], [3, 11], [4, 11], [26, 12], [25, 11], [24, 11],
                             [23, 12]]
        game_state.attempt_spawn(WALL, upgrade_locations)
        if game_state.turn_number > 5:
            game_state.attempt_upgrade(upgrade_locations)
        for location in upgrade_locations:
            for unit in game_state.game_map[location]:
                if unit.health <= 0.6 * unit.max_health:
                    game_state.attempt_remove(location)

        # unique_scored_on_locations = [list(x) for x in set(tuple(x) for x in self.scored_on_locations)]
        # for location in unique_scored_on_locations:
        #     # Build turret one space above so that it doesn't block our own edge spawn locations
        #     build_location = [location[0], location[1]]
        #     if build_location in [[0, 13], [1, 12], [2, 11]]:
        #         game_state.attempt_spawn(TURRET, [[2, 12], [3, 12]])
        #         game_state.attempt_upgrade([[2, 12]])
        #     if build_location in [[27, 13], [26, 12], [25, 11]]:
        #         for location in [[24, 12], [25, 12], [26, 12]]:
        #             if game_state.contains_stationary_unit(location):
        #                 for unit in game_state.game_map[location]:
        #                     if unit.player_index == 0 and (unit.unit_type == WALL):
        #                         game_state.attempt_remove([location])
        #         game_state.attempt_spawn(TURRET, [[24, 11], [25, 11], [24, 12], [25, 12], [26, 12]])
        #         game_state.attempt_spawn(WALL, [[25, 13], [26, 13]])
        #         game_state.attempt_upgrade([[24, 12], [25, 12], [25, 13]])
        # if build_location not in [[24, 10], [25, 11], [26, 12], [27, 13], [23, 9], [0, 13], [1, 12], [2, 11]]:
        #     game_state.attempt_spawn(INTERCEPTOR, build_location, 1)

    def stall_defensive_interceptors(self, game_state):
        for i in range(len(self.scored_on_locations)):
            if game_state.get_resource(MP) >= game_state.type_cost(INTERCEPTOR)[MP]:
                game_state.attempt_spawn(INTERCEPTOR, self.scored_on_locations[i])

    def stall_with_interceptors(self, game_state):
        """
        Send out interceptors at random locations to defend our base from enemy moving units.
        """
        # We can spawn moving units on our edges so a list of all our edge locations
        friendly_edges = game_state.game_map.get_edge_locations(
            game_state.game_map.BOTTOM_LEFT) + game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_RIGHT)

        # Remove locations that are blocked by our own structures 
        # since we can't deploy units there.
        deploy_locations = self.filter_blocked_locations(friendly_edges, game_state)

        # While we have remaining MP to spend lets send out interceptors randomly.
        while game_state.get_resource(MP) >= game_state.type_cost(INTERCEPTOR)[MP] and len(deploy_locations) > 0:
            # Choose a random deploy location.
            deploy_index = random.randint(0, len(deploy_locations) - 1)
            deploy_location = deploy_locations[deploy_index]

            game_state.attempt_spawn(INTERCEPTOR, deploy_location)
            """
            We don't have to remove the location since multiple mobile 
            units can occupy the same space.
            """

    def demolisher_line_strategy(self, game_state):
        """
        Build a line of the cheapest stationary unit so our demolisher can attack from long range.
        """
        # First let's figure out the cheapest unit
        # We could just check the game rules, but this demonstrates how to use the GameUnit class
        stationary_units = [WALL, TURRET, SUPPORT]
        cheapest_unit = WALL
        for unit in stationary_units:
            unit_class = gamelib.GameUnit(unit, game_state.config)
            if unit_class.cost[game_state.MP] < gamelib.GameUnit(cheapest_unit, game_state.config).cost[game_state.MP]:
                cheapest_unit = unit

        # Now let's build out a line of stationary units. This will prevent our demolisher from running into the enemy base.
        # Instead they will stay at the perfect distance to attack the front two rows of the enemy base.
        for x in range(27, 5, -1):
            game_state.attempt_spawn(cheapest_unit, [x, 13])

        # Now spawn demolishers next to the line
        # By asking attempt_spawn to spawn 1000 units, it will essentially spawn as many as we have resources for
        game_state.attempt_spawn(DEMOLISHER, [26, 12], 1000)

    def least_damage_spawn_location(self, game_state, location_options):
        """
        This function will help us guess which location is the safest to spawn moving units from.
        It gets the path the unit will take then checks locations on that path to 
        estimate the path's damage risk.
        """
        damages = []
        # Get the damage estimate each path will take
        for location in location_options:
            path = game_state.find_path_to_edge(location)
            damage = 0
            for path_location in path:
                # Get number of enemy turrets that can attack each location and multiply by turret damage
                damage += len(game_state.get_attackers(path_location, 0)) * gamelib.GameUnit(TURRET,
                                                                                             game_state.config).damage_i
            damages.append(damage)

        # Now just return the location that takes the least damage
        return (min(damages), location_options[damages.index(min(damages))])

    def detect_enemy_unit(self, game_state, unit_type=None, valid_x=None, valid_y=None):
        total_units = 0
        for location in game_state.game_map:
            if game_state.contains_stationary_unit(location):
                for unit in game_state.game_map[location]:
                    if unit.player_index == 1 and (unit_type is None or unit.unit_type in unit_type) and (
                            valid_x is None or location[0] in valid_x) and (valid_y is None or location[1] in valid_y):
                        total_units += 1
        return total_units

    def filter_blocked_locations(self, locations, game_state):
        filtered = []
        for location in locations:
            if not game_state.contains_stationary_unit(location):
                filtered.append(location)
        return filtered

    def yan_fang_si_shou(self, game_state):
        for x in range(27, 8, -1):
            game_state.attempt_spawn(WALL, [x, 9])
        for x in range(9, 3, -1):
            game_state.attempt_spawn(WALL, [x, 18 - x])

        game_state.attempt_spawn(DEMOLISHER, [14, 0], 1)
        pass

    def on_action_frame(self, turn_string):
        """
        This is the action frame of the game. This function could be called 
        hundreds of times per turn and could slow the algo down so avoid putting slow code here.
        Processing the action frames is complicated so we only suggest it if you have time and experience.
        Full doc on format of a game frame at in json-docs.html in the root of the Starterkit.
        """
        # Let's record at what position we get scored on
        state = json.loads(turn_string)
        events = state["events"]
        breaches = events["breach"]
        for breach in breaches:
            location = breach[0]
            unit_owner_self = True if breach[4] == 1 else False
            # When parsing the frame data directly, 
            # 1 is integer for yourself, 2 is opponent (StarterKit code uses 0, 1 as player_index instead)
            if not unit_owner_self:
                gamelib.debug_write("Got scored on at: {}".format(location))
                self.scored_on_locations.append(location)
                gamelib.debug_write("All locations: {}".format(self.scored_on_locations))


if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
