from nes_py.wrappers import JoypadSpace
import gym_super_mario_bros
from gym_super_mario_bros.actions import SIMPLE_MOVEMENT
env = gym_super_mario_bros.make('SuperMarioBros-v0')
env = JoypadSpace(env, SIMPLE_MOVEMENT)

import time


def choose_action(a):
    if a == 1:
        return 2
    else:
        return 1

done = True
action=1
for step in range(5000):
    if done:
        state = env.reset()
    # action = env.action_space.sample()#\
    action = choose_action(action)
    state, reward, done, info = env.step(action)
    time.sleep(0.01)
    space = env.action_space
    env.render()

env.close()