import random
import numpy as np
import matplotlib.pyplot as plt
import time
from minesweeper_MC import Game, LEFT_CLICK

class MonteCarloSolver:
    def __init__(self, game, episodes=2000, gamma=0.95):
        self.game = game
        self.episodes = episodes
        self.gamma = gamma
        self.Q = {}  
        self.returns_sum = {}  
        self.returns_count = {}  
        self.policy = {}  
        self.train_results = []  
        
        self.epsilon_start = 0.9
        self.epsilon_end = 0.1
        
        self.episode_lengths = []
        self.episode_rewards = []

    def observe_state(self):
        visible_grid = []
        for r in range(self.game.squares_y):
            row = []
            for c in range(self.game.squares_x):
                cell = self.game.grid[r][c]
                if cell.is_visible:
                    row.append(cell.bomb_count)
                else:
                    row.append(-1)
            visible_grid.append(tuple(row))
        return tuple(visible_grid)

    def get_local_state(self, row, col, radius=1):
        local_state = []
        for r in range(row - radius, row + radius + 1):
            local_row = []
            for c in range(col - radius, col + radius + 1):
                if 0 <= r < self.game.squares_y and 0 <= c < self.game.squares_x:
                    cell = self.game.grid[r][c]
                    if cell.is_visible:
                        local_row.append(cell.bomb_count)
                    else:
                        local_row.append(-1)
                else:
                    local_row.append(-2)
            local_state.append(tuple(local_row))
        return tuple(local_state)

    def get_unknown_cells(self):
        return [(r, c) for r in range(self.game.squares_y) for c in range(self.game.squares_x)
                if not self.game.grid[r][c].is_visible]

    def get_border_cells(self):
        border_cells = []
        for r in range(self.game.squares_y):
            for c in range(self.game.squares_x):
                if self.game.grid[r][c].is_visible:
                    continue
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if (0 <= nr < self.game.squares_y and 
                            0 <= nc < self.game.squares_x and 
                            self.game.grid[nr][nc].is_visible):
                            border_cells.append((r, c))
                            break
                    else:
                        continue
                    break
        
        return border_cells if border_cells else self.get_unknown_cells()

    def safe_cells_from_logic(self):
        safe_cells = []
        
        for r in range(self.game.squares_y):
            for c in range(self.game.squares_x):
                cell = self.game.grid[r][c]
                if not cell.is_visible or cell.bomb_count == 0:
                    continue
                    
                hidden_neighbors = []
                
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if (0 <= nr < self.game.squares_y and 
                            0 <= nc < self.game.squares_x and 
                            not self.game.grid[nr][nc].is_visible):
                            hidden_neighbors.append((nr, nc))
                
                if len(hidden_neighbors) == cell.bomb_count:
                    continue
                    
                if len(hidden_neighbors) > cell.bomb_count:
                    safe_cells.extend(hidden_neighbors)
        
        return list(set(safe_cells))

    def get_epsilon(self, episode):
        return self.epsilon_end + (self.epsilon_start - self.epsilon_end) * (
            1 - min(1.0, episode / (self.episodes * 0.7))
        )

    def behavior_policy(self, episode_num):
        epsilon = self.get_epsilon(episode_num)
        state = self.observe_state()
        if all(all(cell == -1 for cell in row) for row in state):
            corners = [(0, 0), (0, self.game.squares_x-1), 
                      (self.game.squares_y-1, 0), (self.game.squares_y-1, self.game.squares_x-1)]
            for corner in corners:
                if not self.game.grid[corner[0]][corner[1]].is_visible:
                    return corner
            edges = []
            for r in range(self.game.squares_y):
                edges.extend([(r, 0), (r, self.game.squares_x-1)])
            for c in range(self.game.squares_x):
                edges.extend([(0, c), (self.game.squares_y-1, c)])
            random.shuffle(edges)
            for edge in edges:
                if not self.game.grid[edge[0]][edge[1]].is_visible:
                    return edge
        
        safe_cells = self.safe_cells_from_logic()
        if safe_cells:
            return random.choice(safe_cells)
        
        border_cells = self.get_border_cells()
        if not border_cells:
            return None
        
        if random.random() < epsilon:
            
            return random.choice(border_cells)
        else:
            best_action = None
            best_value = float('-inf')
            
            for r, c in border_cells:
                local_state = self.get_local_state(r, c)
                if (local_state, (r, c)) in self.Q:
                    q_value = self.Q[(local_state, (r, c))]
                    if q_value > best_value:
                        best_value = q_value
                        best_action = (r, c)
            
            if best_action is not None:
                return best_action
            
            return random.choice(border_cells)

    def click_cell(self, row, col):
        self.game.click_handle(row, col, LEFT_CLICK)
        self.game.check_victory()

    def generate_episode(self, episode_num, max_steps=100):
        self.game.reset_game(keep_bombs=False)
        episode = []
        visited_states_actions = set()
        states_actions_history = []  
        
        step = 0
        episode_reward = 0
        
        while not self.game.game_lost and not self.game.game_won and step < max_steps:
            action = self.behavior_policy(episode_num)
            if action is None:
                break
                
            local_state = self.get_local_state(action[0], action[1])
            if (local_state, action) in visited_states_actions:
                break
                
            visible_before = sum(1 for row in self.game.grid for cell in row if cell.is_visible)
            self.click_cell(*action)
            
            visible_after = sum(1 for row in self.game.grid for cell in row if cell.is_visible)
            new_cells_revealed = visible_after - visible_before
            
            if self.game.game_won:
                reward = 5 
            elif self.game.game_lost:
                reward = -5
            else:
                reward = 0.5 * new_cells_revealed - 0.1
                
            states_actions_history.append((local_state, action, reward))
            visited_states_actions.add((local_state, action))
            episode_reward += reward
            step += 1
            
            if (local_state, action) not in [(s, a) for s, a, _ in episode]:
                episode.append((local_state, action, reward))
        
        self.episode_lengths.append(step)
        self.episode_rewards.append(episode_reward)
        
        self.train_results.append(1 if self.game.game_won else 0)
        
        return episode, states_actions_history

    def update_q_values(self, episode_history):
        G = 0  
        for t in range(len(episode_history) - 1, -1, -1):
            state, action, reward = episode_history[t]
            G = self.gamma * G + reward
            
            sa_pair = (state, action)
            
            self.returns_count[sa_pair] = self.returns_count.get(sa_pair, 0) + 1
            learning_rate = 1.0 / self.returns_count[sa_pair]  
            current_estimate = self.Q.get(sa_pair, 0)
            
            self.Q[sa_pair] = current_estimate + learning_rate * (G - current_estimate)

    def extract_policy(self):
        self.policy = {}
        
        state_actions = {}
        for (state, action), value in self.Q.items():
            if state not in state_actions:
                state_actions[state] = []
            state_actions[state].append((action, value))
        
        for state, actions in state_actions.items():
            if actions:
                best_action = max(actions, key=lambda x: x[1])[0]
                self.policy[state] = best_action

    def train(self, verbose=True):
        if verbose:
            print("Starting training...")
        
        window_size = 100
        win_rates = []
        
        for ep in range(1, self.episodes + 1):
            _, episode_history = self.generate_episode(ep)
            
            self.update_q_values(episode_history)
            
            if ep % window_size == 0:
                recent_win_rate = sum(self.train_results[-window_size:]) / window_size
                win_rates.append(recent_win_rate)
                
                if verbose:
                    print(f"Episode {ep}/{self.episodes} - Recent win rate: {recent_win_rate:.2f}")
                    print(f"Q table size: {len(self.Q)}")
                    print(f"Average episode length: {sum(self.episode_lengths[-window_size:]) / window_size:.1f}")
        
        self.extract_policy()
        
        if verbose:
            print("Training completed!")
            print(f"Final Q table size: {len(self.Q)}")
            print(f"Final policy size: {len(self.policy)}")
        
        return win_rates

    def play_game(self, use_policy=True, max_steps=100):
        self.game.reset_game(keep_bombs=False)
        steps = 0
        
        while not self.game.game_lost and not self.game.game_won and steps < max_steps:
            if use_policy:
                found_action = False
                unknown_cells = self.get_unknown_cells()
                
                if not unknown_cells:
                    break
                
                for r, c in unknown_cells:
                    local_state = self.get_local_state(r, c)
                    if local_state in self.policy:
                        action = self.policy[local_state]
                        found_action = True
                        break
                
                if not found_action:
                    safe_cells = self.safe_cells_from_logic()
                    if safe_cells:
                        action = random.choice(safe_cells)
                    else:
                        border_cells = self.get_border_cells()
                        action = random.choice(border_cells) if border_cells else random.choice(unknown_cells)
            else:
                action = self.behavior_policy(self.episodes)  
            
            if action is None:
                break
                
            self.click_cell(*action)
            steps += 1
        
        return self.game.game_won, steps

    def evaluate(self, num_games=100, use_policy=True):
        wins = 0
        total_steps = 0
        
        for _ in range(num_games):
            win, steps = self.play_game(use_policy=use_policy)
            if win:
                wins += 1
                total_steps += steps
        
        win_rate = wins / num_games
        avg_steps = total_steps / wins if wins > 0 else 0
        
        print(f"Evaluation over {num_games} games:")
        print(f"Win rate: {win_rate:.2f}")
        print(f"Average steps to win: {avg_steps:.1f}")
        
        return win_rate, avg_steps

    def test_win_rate(self, num_games=100, verbose=True):
        wins = 0
        losses = 0
        total_exploration = 0
        start_time = time.time()
        
        for i in range(1, num_games + 1):
            self.game.reset_game(keep_bombs=False)
            game_over = False
            steps = 0
            
            while not game_over and steps < 100:  
                action = self.behavior_policy(self.episodes)  
                
                if action is None:
                    break
                
                self.click_cell(*action)
                steps += 1
                
                if self.game.game_won:
                    wins += 1
                    game_over = True
                elif self.game.game_lost:
                    losses += 1
                    game_over = True
            
            total_exploration += 1 if self.game.game_won else 0
            
            if verbose and i % 10 == 0:
                print(f"Progress: {i}/{num_games} games played")
        
        win_rate = (wins / num_games) * 100
        avg_exploration = (total_exploration / num_games) * 100
        time_taken = time.time() - start_time
        
        if verbose:
            print("----- RESULTS -----")
            print(f"Games played: {num_games}")
            print(f"Number of mines: {self.game.num_bombs}")
            print(f"Grid size: {self.game.squares_x}x{self.game.squares_y}")
            print(f"Wins: {wins}")
            print(f"Losses: {losses}")
            print(f"Win rate: {win_rate:.2f}%")
            print(f"Average Exploration Rate: {avg_exploration:.2f}%")
            print(f"Time taken: {time_taken:.2f} seconds")
        
        return win_rate

    def plot_training_progress(self):
        plt.figure(figsize=(15, 10))
        
        plt.subplot(2, 2, 1)
        window_size = 100
        win_rates = []
        for i in range(window_size, len(self.train_results) + 1, window_size):
            win_rates.append(sum(self.train_results[i-window_size:i]) / window_size)
        
        plt.plot(range(window_size, len(self.train_results) + 1, window_size), win_rates, 'b-o')
        plt.title('Win Rate (per 100 episodes)')
        plt.xlabel('Episodes')
        plt.ylabel('Win Rate')
        plt.grid(True)
        
        plt.subplot(2, 2, 2)
        avg_lengths = []
        for i in range(window_size, len(self.episode_lengths) + 1, window_size):
            avg_lengths.append(sum(self.episode_lengths[i-window_size:i]) / window_size)
        
        plt.plot(range(window_size, len(self.episode_lengths) + 1, window_size), avg_lengths, 'g-o')
        plt.title('Average Episode Length (per 100 episodes)')
        plt.xlabel('Episodes')
        plt.ylabel('Steps')
        plt.grid(True)
        
        plt.subplot(2, 2, 3)
        avg_rewards = []
        for i in range(window_size, len(self.episode_rewards) + 1, window_size):
            avg_rewards.append(sum(self.episode_rewards[i-window_size:i]) / window_size)
        
        plt.plot(range(window_size, len(self.episode_rewards) + 1, window_size), avg_rewards, 'r-o')
        plt.title('Average Episode Reward (per 100 episodes)')
        plt.xlabel('Episodes')
        plt.ylabel('Reward')
        plt.grid(True)
        
        plt.subplot(2, 2, 4)
        plt.hist(list(self.Q.values()), bins=20)
        plt.title(f'Q-Values Distribution (table size: {len(self.Q)})')
        plt.xlabel('Q-Value')
        plt.ylabel('Frequency')
        plt.grid(True)
        
        plt.tight_layout()
        plt.show()