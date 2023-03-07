import matplotlib.pyplot as plt
import numpy as np


def moving_average(a, n=3) :
    ret = np.cumsum(a, dtype=float)
    ret[n:] = ret[n:] - ret[:-n]
    ma = ret[n - 1:] / n
    pad = np.zeros(n-1) * np.nan
    ma = np.concatenate([pad, ma])
    return ma


def integrate(a, n_buckets=60):
    n = a.shape[0]
    buckets = []
    for i in range(n_buckets):
        start = i
        stop = i + 1

        left = int(start / n_buckets * n)
        right = int(stop / n_buckets * n)

        data = a[left:right]
        integrated = np.sum(np.abs(data))
        buckets.append(integrated)

    return np.array(buckets)


def main():
    PATH = "data/botharms_230301_155959/amplifier_data.txt"
    T_PATH = "data/botharms_230301_155959/t_amplifier.txt"
    fig, axs = plt.subplots(4)
    ax1 = axs[0]
    ax2 = axs[1]
    ax3 = axs[2]
    ax4 = axs[3]

    data = np.loadtxt(PATH)
    ts = np.loadtxt(T_PATH)

    START = 0
    STOP = 60

    LEFT = int(START / 60 * data.shape[1])
    RIGHT = int(STOP / 60 * data.shape[1])
    data = data[:, LEFT:RIGHT]
    ts = ts[LEFT:RIGHT]

    ax1.plot(ts, data[0], label="Signal 1")
    ax1.set_title("Stream 1")
    ax1.plot(ts, data[1], label="Signal 2")

    # # moving averages
    # ma1 = moving_average(data[0], 500)
    # ma2 = moving_average(data[1], 500)
    # ma3 = moving_average(data[0] - data[1], 500)
    # ax2.plot(ts, ma1)
    # ax2.plot(ts, ma2)
    # ax2.plot(ts, ma3)

    # ingegrations
    i1 = integrate(data[0], 600)
    i2 = integrate(data[1], 600)
    t_ints = list(range(600))

    ma1 = moving_average(i1, 20)
    ma2 = moving_average(i2, 20)
    ax2.plot(t_ints, ma1, label="AbsIntegration of Signal 1")
    ax2.plot(t_ints, ma2, label="AbsIntegration of Signal 2")
    # ax2.plot(t_ints, i1 - i2)

    # ax2.set_title("Stream 2")
    ax3.plot(t_ints, i1 - i2, label="Difference in Integrations")
    ma_diff = moving_average(i1 - i2, 20)
    # ma_diff = moving_average(i1, 20) - moving_average(i2, 20)
    ax3.plot(t_ints, ma_diff, label="MA50")
    ax3.set_title("Stream 1 - Stream 2")
    fig.suptitle(f"{START} seconds to {STOP} seconds")


    # extracting control signal
    righthand = ma2 > 2e5
    diff = ma_diff > 1e5

    bothhands = np.logical_and(diff, righthand)
    lefthand_only = np.logical_and(righthand, ~bothhands)
    righthand_only = np.logical_and(diff, ~bothhands)
    nothing = np.logical_and(~diff, ~righthand)

    controls = np.zeros(len(t_ints))
    controls[nothing] = 0
    controls[lefthand_only] = 1
    controls[righthand_only] = 2
    controls[bothhands] = 3

    ax4.plot(t_ints, controls)

    ax1.legend()
    ax2.legend()
    ax3.legend()
    ax4.legend()
    plt.show()


if __name__ == '__main__':
    main()