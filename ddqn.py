import argparse
import gym
import numpy as np
import random
import math
from itertools import count

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.autograd import Variable

parser = argparse.ArgumentParser(description='deep q learning')
parser.add_argument('--gamma', type=float, default=0.99, metavar='G',
                    help='discount factor (default: 0.99)')
parser.add_argument('--seed', type=int, default=543, metavar='N',
                    help='random seed (default: 543)')
parser.add_argument('--render', action='store_true',
                    help='render the environment')
parser.add_argument('--log-interval', type=int, default=50, metavar='N',
                    help='interval between training status logs (default: 50)')
args = parser.parse_args()

env = gym.make('CartPole-v0')
env.seed(args.seed)
torch.manual_seed(args.seed)

STATE_DIM = env.observation_space.shape[0]
ACTION_DIM = env.action_space.n

class ReplayMemory(object):

    def __init__(self, capacity):
        self.capacity = capacity
        self.memory = []
        self.position = 0

    def push(self, transition):
        """Saves a transition."""
        if len(self.memory) < self.capacity:
            self.memory.append(None)
        self.memory[self.position] = transition
        self.position = (self.position + 1) % self.capacity

    def sample(self, batch_size):
        return random.sample(self.memory, batch_size)

    def __len__(self):
        return len(self.memory)

FloatTensor = torch.FloatTensor
LongTensor = torch.LongTensor 
ByteTensor = torch.ByteTensor 
Tensor = FloatTensor

class DQN(nn.Module):
    def __init__(self,state_dim,action_dim,hidden_size):
        super(DQN, self).__init__()
        
        self.l1 = nn.Linear(state_dim, hidden_size)
        self.l2 = nn.Linear(hidden_size,hidden_size)
        self.l3 = nn.Linear(hidden_size, action_dim)

    def forward(self, x):
        model = torch.nn.Sequential(
            self.l1,
            nn.ReLU(),
            self.l2,
            nn.ReLU(),
            self.l3
        )
        return model(x)

eval_net = DQN(STATE_DIM,ACTION_DIM,128)
target_net = DQN(STATE_DIM,ACTION_DIM,128)
target_net.load_state_dict(eval_net.state_dict())
target_net.eval()

optimizer = optim.Adam(eval_net.parameters(), lr=1e-2)
memory = ReplayMemory(10000)
BATCH_SIZE = 128
EPS_START = 0.9
EPS_END = 0.05
EPS_DECAY = 200
TARGET_UPDATE = 10
steps_done = 0

def select_action(state):
    global steps_done
    sample = random.random()
    eps_rate = EPS_END + (EPS_START - EPS_END) * \
        math.exp(-1. * steps_done / EPS_DECAY)
    steps_done += 1
    if sample > eps_rate:
        with torch.no_grad():
            return eval_net(Variable(state)).data.max(1)[1].view(1, 1)
    else:
        return LongTensor([[random.randrange(2)]])

def update_net():
    if len(memory) < BATCH_SIZE:
        return
    transitions = memory.sample(BATCH_SIZE)
    batch_state, batch_action, batch_next_state, batch_reward, batch_done = zip(*transitions)
    batch_state = Variable(torch.cat(batch_state))
    batch_action = Variable(torch.cat(batch_action))
    batch_reward = Variable(torch.cat(batch_reward))
    batch_next_state = Variable(torch.cat(batch_next_state))
    batch_done = Variable(torch.cat(batch_done))

    # compute Q(s_t, a) - the model computes Q(s_t), then we select the columns of actions taken
    current_q_states_values = eval_net(batch_state)
    current_q_values = current_q_states_values.gather(1, batch_action)
    next_q_states_values = eval_net(batch_next_state)
    # compute target Q(s_{t+1}) for all next states and all actions
    target_next_q_states_values = target_net(batch_next_state)
    # use Q net to get next actions
    max_next_actions = next_q_states_values.detach().max(1)[1].unsqueeze(1)
    # use target Q to get max Q values
    next_q_values = target_next_q_states_values.gather(1, max_next_actions).squeeze(1)
    expected_q_values = (batch_reward + (1.0 - batch_done) * args.gamma * next_q_values).unsqueeze(1)
    # loss is measured from error between current and newly expected Q values
    loss = nn.MSELoss()(current_q_values, Variable(expected_q_values))

    # backpropagation of loss to NN
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

def main():
    running_reward = 10
    print("reward threshold", env.spec.reward_threshold)
    for i_episode in count(1):
        # Initialize the environment and state
        state = env.reset()
        for t in range(10000):
            # Select and perform an action
            action = select_action(FloatTensor([state]))
            next_state, reward, done, _ = env.step(action.item())
        
            if done:
                reward = -1

            # Store the transition in memory
            transition = (FloatTensor([state]), action, FloatTensor([next_state]), FloatTensor([reward]), FloatTensor([done]))
            memory.push(transition)
            state = next_state
            # Perform one step of the optimization (on the target network)
            update_net()
            if done:
                break
        
        running_reward = running_reward * 0.99 + t * 0.01
        
        if i_episode % args.log_interval == 0:
            print('Episode {}\tLast length: {:5d}\tAverage length: {:.2f}'.format(
                i_episode, t+1, running_reward))
        if running_reward > env.spec.reward_threshold:
            print("Solved! Running reward is now {} and "
                  "the last episode runs to {} time steps!".format(running_reward, t+1))
            break
        # Update the target network
        if i_episode % TARGET_UPDATE == 0:
            target_net.load_state_dict(eval_net.state_dict())
    
    # test
    for i_episode in range(10):
        state = env.reset()
        for t in range(1000):
            env.render()
            pred = eval_net(FloatTensor([state]))
            values = pred.detach().numpy()
            action = np.argmax(values)
            state, reward, done, info = env.step(action)
            if done:
                print("Episode finished after {} timesteps".format(t+1))
                break

    env.close()


if __name__ == '__main__':
    main()
