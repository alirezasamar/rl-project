import torch
from torch import Tensor,nn
import gym
from torch.distributions import Categorical
import torch.optim as optim
from torch.utils.tensorboard import SummaryWriter
writer = SummaryWriter()

NO_EPOCHS = 1000
NO_STEPS = 2048
GAMMA = 0.99
LAMB = 0.95
CLIP = 0.2
lr = 3e-4
batch_size = 64

class Critic(nn.Module):
    def __init__(self,obs, hidden_size = 64):
        super().__init__()

        self.net = nn.Sequential(
            nn.Linear(obs,hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, 1)
            )

    def forward(self,x):
        return self.net(x)

class Actor(nn.Module):
    def __init__(self,obs, n_actions, hidden_size = 64):
        super().__init__()

        self.net = nn.Sequential(
            nn.Linear(obs,hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, n_actions)
            )
    def forward(self,x):
        logits = self.net(x)
        logits = torch.nan_to_num(logits)
        dist = Categorical(logits=logits)
        action = dist.sample()

        return dist,action

class ActorCritic():
    def __init__(self, critic, actor):
        self.critic = critic
        self.actor = actor

    @torch.no_grad()
    def __call__(self, state):
        dist, action = self.actor(state)
        probs = dist.log_prob(action)
        val = self.critic(state)

        return dist, action, probs, val



env = gym.make("LunarLander-v2")
state = torch.Tensor(env.reset())
obs = env.observation_space.shape[0]
actions = env.action_space.n

actor = Actor(obs,actions)
critic = Critic(obs)

actor_optimizer = optim.Adam(actor.parameters(), lr=lr)
critic_optimizer = optim.Adam(critic.parameters(), lr=lr)

agent = ActorCritic(critic,actor)

def gae(rewards, values):

    rs = rewards
    vals = values

    x = []
    for i in range(len(rs)-1):
        x.append(rs[i]+GAMMA*vals[i+1] - vals[i])

    a = discount(x, GAMMA * LAMB)
    return a

def discount(rewards, gamma):

    rs = []
    sum_rs = 0

    for r in reversed(rewards):
        sum_rs = (sum_rs * gamma) + r
        rs.append(sum_rs)


    return list(reversed(rs))

def update(states,actions,probs,vals,advs):

    dist, _ = actor(state)
    prob = dist.log_prob(action)
    ratio = torch.exp(prob - prob_old)
    #PPO update
    clip = torch.clamp(ratio, 1 - CLIP, 1 + CLIP) * adv
    #negative gradient descent - gradient ascent
    actor_loss = -(torch.min(ratio * adv, clip)).mean()

    val_new = self.critic(state)
    #MSE
    critic_loss = (val - val_new).pow(2).mean()

    actor_optimizer.zero_grad()
    critic_optimizer.zero_grad()

    actor_loss.backward()
    critic_loss.backward()

    actor_optimizer.step()
    critic_optimizer.step()

    return actor_loss, critic_loss




for e in range(NO_EPOCHS):
    states = []
    actions = []
    probs = []
    advs = []
    vals = []
    ep_rewards = []
    ep_vals = []
    epoch_rewards = []
    avg_reward = 0
    for i in range(NO_STEPS):
        print("Step: ",i)
        _, action, ps, val = agent(state)
        next_state, reward, done, _ = env.step(action.item())

        states.append(state)
        actions.append(action)
        probs.append(ps)
        ep_rewards.append(reward)
        ep_vals.append(val)

        state = torch.Tensor(next_state)

        if done or i==NO_STEPS-1:

            if i==NO_STEPS-1 and not done:

                #bootstrap value of last state if epoch ends early
                with torch.no_grad():

                    _,_,_,val = agent(state)
                    new_val = val.item()
            else:
                new_val = 0

            #reward is approximated by value function if bootstrap, otherwise no reward for end of episode
            ep_rewards.append(new_val)
            ep_vals.append(new_val)

            vals.extend(discount(ep_rewards,GAMMA)[:-1])
            advs.extend(gae(ep_rewards,ep_vals))

            epoch_rewards.append(sum(ep_rewards))

    for i in range(0,NO_STEPS,batch_size):
        actor_loss, critic_loss = update(states[i:batch_size],
                                        actions[i:batch_size],
                                        probs[i:batch_size],
                                        vals[i:batch_size],
                                        advs[i:batch_size])
    print("[ Epoch :",e,"- actor_loss:",actor_loss,", critic_loss:",critic_loss,", avg_reward:",sum(epoch_rewards)/len(epoch_rewards))


