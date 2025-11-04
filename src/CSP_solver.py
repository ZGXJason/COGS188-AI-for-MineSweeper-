import sys
import random
import time
from copy import deepcopy
LEFT_CLICK = 1
RIGHT_CLICK = 3
NSQUARES_X = 16
NSQUARES_Y = 16

def get_neighbors(r, c, max_rows, max_cols):
    neighbors = []
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < max_rows and 0 <= nc < max_cols:
                neighbors.append((nr, nc))
    return neighbors

def get_frontier_cells(game):
    frontier = set()
    for r in range(game.squares_y):
        for c in range(game.squares_x):
            cell = game.grid[r][c]
            if not cell.is_visible and not cell.has_flag:
                for nr, nc in get_neighbors(r, c, game.squares_y, game.squares_x):
                    neighbor = game.grid[nr][nc]
                    if neighbor.is_visible and neighbor.bomb_count > 0:
                        frontier.add((r, c))
                        break
    return frontier

def get_constraints(game, frontier):
    constraints = {}
    for r in range(game.squares_y):
        for c in range(game.squares_x):
            cell = game.grid[r][c]
            if cell.is_visible and cell.bomb_count > 0:
                adj_frontier = []
                flagged = 0
                for nr, nc in get_neighbors(r, c, game.squares_y, game.squares_x):
                    if game.grid[nr][nc].has_flag:
                        flagged += 1
                    elif (nr, nc) in frontier:
                        adj_frontier.append((nr, nc))
                required = cell.bomb_count - flagged
                if adj_frontier and 0 <= required <= len(adj_frontier):
                    constraints[(r, c)] = (required, adj_frontier)
    return constraints

def group_frontier_by_constraints(frontier, constraints):
    graph = {cell: set() for cell in frontier}
    for _, (req, cells) in constraints.items():
        for cellA in cells:
            for cellB in cells:
                if cellA != cellB:
                    graph[cellA].add(cellB)
                    graph[cellB].add(cellA)

    clusters = []
    visited = set()
    for cell in frontier:
        if cell not in visited:
            stack = [cell]
            comp = []
            while stack:
                cur = stack.pop()
                if cur in visited:
                    continue
                visited.add(cur)
                comp.append(cur)
                for nxt in graph[cur]:
                    if nxt not in visited:
                        stack.append(nxt)
            clusters.append(comp)
    return clusters

def get_cluster_constraints(cluster, constraints):
    cluster_set = set(cluster)
    cluster_constraints = {}
    for clue, (req, frontier_cells) in constraints.items():
        intersected = [fc for fc in frontier_cells if fc in cluster_set]
        if intersected:
            cluster_constraints[clue] = (req, intersected)
    return cluster_constraints

def valid_partial(assignment, constraints_list):
    for req, indices in constraints_list:
        assigned_sum = 0
        unassigned = 0
        for idx in indices:
            val = assignment[idx]
            if val == -1:
                unassigned += 1
            else:
                assigned_sum += val
        if assigned_sum > req:
            return False
        if assigned_sum + unassigned < req:
            return False
    return True

def backtrack_csp(i, assignment, constraints_list, results, n):
    if i == n:
        for req, indices in constraints_list:
            if sum(assignment[idx] for idx in indices) != req:
                return
        results['count'] += 1
        for j in range(n):
            if assignment[j] == 1:
                results['bomb_counts'][j] += 1
        return

    for val in [0, 1]:
        assignment[i] = val
        if valid_partial(assignment, constraints_list):
            backtrack_csp(i+1, assignment, constraints_list, results, n)
    assignment[i] = -1  

def csp_cluster_solver(cluster, cluster_constraints):
    n = len(cluster)
    index_map = {cell: i for i, cell in enumerate(cluster)}
    constraints_list = []
    for clue, (req, frontier_cells) in cluster_constraints.items():
        indices = [index_map[cell] for cell in frontier_cells]
        constraints_list.append((req, indices))
    results = {
        'count': 0,
        'bomb_counts': [0]*n
    }
    assignment = [-1]*n

    backtrack_csp(0, assignment, constraints_list, results, n)

    if results['count'] == 0:
        return {cell: 1.0 for cell in cluster}
    else:
        probs = {}
        for i, cell in enumerate(cluster):
            probs[cell] = results['bomb_counts'][i] / results['count']
        return probs
def csp_solver(game):
    hidden_cells = [
        (r, c) for r in range(game.squares_y) for c in range(game.squares_x)
        if (not game.grid[r][c].is_visible and not game.grid[r][c].has_flag)
    ]
    if not game.init:
        if hidden_cells:
            return random.choice(hidden_cells)
        else:
            return None
    frontier = get_frontier_cells(game)
    constraints = get_constraints(game, frontier)

    if not frontier:
        if hidden_cells:
            return random.choice(hidden_cells)
        return None

    clusters = group_frontier_by_constraints(frontier, constraints)
    probabilities = {}
    for cluster in clusters:
        cluster_constraints = get_cluster_constraints(cluster, constraints)
        cluster_probs = csp_cluster_solver(cluster, cluster_constraints)
        probabilities.update(cluster_probs)
    flagged_count = sum(
        1 for r in range(game.squares_y) for c in range(game.squares_x)
        if game.grid[r][c].has_flag
    )
    total_unrevealed = len(hidden_cells)
    default_prob = 1.0
    if total_unrevealed > 0:
        bombs_left = game.num_bombs - flagged_count
        default_prob = bombs_left / total_unrevealed

    for (r, c) in hidden_cells:
        if (r, c) not in probabilities:
            probabilities[(r, c)] = default_prob
    guaranteed_safe = [cell for cell, prob in probabilities.items() if prob == 0.0]
    if guaranteed_safe:
        return random.choice(guaranteed_safe)

    if hidden_cells:
        return random.choice(hidden_cells)

    return None


class HeadlessGame:
    
    class Cell:
        def __init__(self, x, y):
            self.x = x
            self.y = y
            self.is_visible = False
            self.has_bomb = False
            self.bomb_count = 0
            self.test = False
            self.has_flag = False
            
        def count_bombs(self, max_rows, max_cols):
            if not self.test:
                self.test = True
                if not self.has_bomb:
                    for col in range(self.x - 1, self.x + 2):
                        for row in range(self.y - 1, self.y + 2):
                            if (row >= 0 and row < max_rows and
                                col >= 0 and col < max_cols and
                                not (col == self.x and row == self.y) and
                                game.grid[row][col].has_bomb):
                                self.bomb_count += 1
        
        def open_neighbours(self, max_rows, max_cols):
            col = self.x
            row = self.y
            for row_off in range(-1, 2):
                for col_off in range(-1, 2):
                    if ((row_off == 0 or col_off == 0) and row_off != col_off and
                        row + row_off >= 0 and col + col_off >= 0 and
                        row + row_off < max_rows and col + col_off < max_cols):
                        cell = game.grid[row + row_off][col + col_off]
                        cell.count_bombs(game.squares_y, game.squares_x)
                        if (not cell.is_visible and not cell.has_bomb):
                            cell.is_visible = True
                            cell.has_flag = False
                            if cell.bomb_count == 0:
                                cell.open_neighbours(game.squares_y, game.squares_x)
    
    def __init__(self, num_bombs=40):
        self.squares_x = NSQUARES_X
        self.squares_y = NSQUARES_Y
        self.grid = [[self.Cell(x, y) for x in range(self.squares_x)] for y in range(self.squares_y)]
        self.init = False
        self.game_lost = False
        self.game_won = False
        self.num_bombs = num_bombs
        self.flag_count = 0
    
    def place_bombs(self, row, column):
        bombplaced = 0
        while bombplaced < self.num_bombs:
            x = random.randrange(self.squares_y)
            y = random.randrange(self.squares_x)
            if (abs(x - row) > 1 or abs(y - column) > 1) and not self.grid[x][y].has_bomb:
                self.grid[x][y].has_bomb = True
                bombplaced += 1
        self.count_all_bombs()
    
    def count_all_bombs(self):
        for row in range(self.squares_y):
            for column in range(self.squares_x):
                self.grid[row][column].count_bombs(self.squares_y, self.squares_x)
    
    def check_victory(self):
        count = 0
        total = self.squares_x * self.squares_y
        for row in range(self.squares_y):
            for column in range(self.squares_x):
                if self.grid[row][column].is_visible:
                    count += 1
        if ((total - count) == self.num_bombs) and not self.game_lost:
            self.game_won = True
            return True
        return False
    
    def count_flags(self):
        total_flags = 0
        for row in range(self.squares_y):
            for column in range(self.squares_x):
                if self.grid[row][column].has_flag:
                    total_flags += 1
        self.flag_count = total_flags
    
    def click_handle(self, row, column, button):
        if button == LEFT_CLICK and not self.grid[row][column].has_flag:
            if not self.game_lost:
                if not self.init:
                    self.place_bombs(row, column)
                    self.init = True
                self.grid[row][column].is_visible = True
                self.grid[row][column].has_flag = False
                if self.grid[row][column].has_bomb:
                    self.game_lost = True
                    return False
                if self.grid[row][column].bomb_count == 0 and not self.grid[row][column].has_bomb:
                    self.grid[row][column].open_neighbours(self.squares_y, self.squares_x)
                return self.check_victory()
        elif button == RIGHT_CLICK:
            if not self.grid[row][column].has_flag:
                if self.flag_count < self.num_bombs and not self.grid[row][column].is_visible:
                    self.grid[row][column].has_flag = True
            else:
                self.grid[row][column].has_flag = False
            self.count_flags()
        return False

    def get_revealed_percentage(self):
        """Calculate how much of the board has been revealed"""
        visible_count = sum(1 for row in range(self.squares_y) 
                            for col in range(self.squares_x) 
                            if self.grid[row][col].is_visible)
        total_safe_cells = self.squares_x * self.squares_y - self.num_bombs
        return (visible_count / total_safe_cells) * 100 if total_safe_cells > 0 else 0

def test_solver(num_games=100, num_mines=10):
    """Test the CSP solver over multiple games"""
    
    global game  
    
    wins = 0
    losses = 0
    exploration_rates = []
    start_time = time.time()
    
    for game_num in range(1, num_games + 1):
        if game_num % 10 == 0:
            print(f"Progress: {game_num}/{num_games} games played")
        
        game = HeadlessGame(num_bombs=num_mines)
        
        game_over = False
        while not game_over:
            move = csp_solver(game)
            
            if move is None:
                game.game_lost = True
                losses += 1
                break
                
            row, col = move
            victory = game.click_handle(row, col, LEFT_CLICK)
            
            if victory:
                wins += 1
                exploration_rates.append(game.get_revealed_percentage())
                game_over = True
            elif game.game_lost:
                losses += 1
                exploration_rates.append(game.get_revealed_percentage())
                game_over = True
    
    end_time = time.time()
    time_taken = end_time - start_time
    
    print("----- RESULTS -----")
    print(f"Games played: {num_games}")
    print(f"Number of mines: {num_mines}")
    print(f"Grid size: {NSQUARES_X}x{NSQUARES_Y}")
    print(f"Wins: {wins}")
    print(f"Losses: {losses}")
    print(f"Win rate: {(wins/num_games)*100:.2f}%")
    print(f"Average Exploration Rate: {sum(exploration_rates)/len(exploration_rates):.2f}%")
    print(f"Time taken: {time_taken:.2f} seconds")
    
    return {
        "games": num_games,
        "mines": num_mines,
        "wins": wins,
        "losses": losses,
        "win_rate": (wins/num_games)*100,
        "avg_exploration": sum(exploration_rates)/len(exploration_rates),
        "time_taken": time_taken
    }

game = None

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test CSP solver for Minesweeper")
    parser.add_argument("--games", type=int, default=100, help="Number of games to test")
    parser.add_argument("--mines", type=int, default=10, help="Number of mines in each game")
    args = parser.parse_args()
    test_solver(num_games=args.games, num_mines=args.mines)