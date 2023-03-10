from PySide6 import QtWidgets, QtCore
from functools import partial

import pyqtgraph as pg
import struct
import time, socket
import enum
import numpy as np
import itertools


COMMAND_BUFFER_SIZE = 1024
WAVEFORM_BUFFER_SIZE = 400000

TICK_INTERVAL = 0.1
CALIBRATION_ELAPSED = 5
SERVER_WAIT = 0.05

class StateMachineModes(enum.Enum):
    IDLE = "Idle"
    CALIBRATE_P1_RELAX = "Player 1 Relax"
    CALIBRATE_P1_FLEX = "Player 1 Flex"
    CALIBRATE_P2_RELAX = "Player 2 Relax"
    CALIBRATE_P2_FLEX = "Player 2 Flex"


class PortListWidgetItem(QtWidgets.QListWidgetItem):
    def __lt__(self, other):
        try:
            return float(self.text().split('-')[1]) < float(other.text().split('-')[1])
        except Exception:
            return QListWidgetItem.__lt__(self, other)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, scommand, swaveform, timestep):
        super().__init__()

        self.scommand = scommand
        self.swaveform = swaveform
        self.timestep = timestep

        self._mode = StateMachineModes.IDLE
        self._state_machine_count_down = 0
        self._tick_count = 0

        #self._record_state = False
        self.calibration_data = {
            StateMachineModes.CALIBRATE_P1_RELAX: 0,
            StateMachineModes.CALIBRATE_P1_FLEX: 0,
            StateMachineModes.CALIBRATE_P2_RELAX: 0,
            StateMachineModes.CALIBRATE_P2_FLEX: 0
        }

        self.setWindowTitle("EMG Game Controller")

        self.central_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.vbox0 = QtWidgets.QVBoxLayout(self.central_widget)
    
        self.hbox0 = QtWidgets.QHBoxLayout()

        self.port_selection_grp = QtWidgets.QGroupBox()
        self.port_selection_grp.setTitle("Port Selection")
        self.hbox0.addWidget(self.port_selection_grp)

        self.port_selection_grp_vbox0 = QtWidgets.QVBoxLayout()
        self.port_selection_grp.setLayout(self.port_selection_grp_vbox0)
        self.port_selection_grp.setMaximumWidth(200)

        self.port_selection_grp_vbox0.addWidget(QtWidgets.QLabel("Available Ports:"))
        self.available_ports = QtWidgets.QListWidget()
        for x in range(32):
            self.available_ports.addItem(PortListWidgetItem(f"A-{x:03}"))
            self.available_ports.addItem(PortListWidgetItem(f"B-{x:03}"))
        self.available_ports.itemDoubleClicked.connect(self.add_to_selected_ports)
        self.available_ports.setSortingEnabled(True)
        self.port_selection_grp_vbox0.addWidget(self.available_ports)

        self.port_selection_grp_vbox0.addWidget(QtWidgets.QLabel("Selected Ports:"))
        self.selected_ports = QtWidgets.QListWidget()
        self.selected_ports.itemDoubleClicked.connect(self.remove_from_selected_ports)
        self.selected_ports.setSortingEnabled(True)
        self.port_selection_grp_vbox0.addWidget(self.selected_ports)

        self.vbox_plots = QtWidgets.QVBoxLayout()

        self.plot_zone_td0 = pg.PlotWidget()
        self.plot_zone_td0.setMinimumWidth(500)
        self.plot_zone_td0.setTitle("Player 1")
        self.plot_zone_td0.setLabel(axis='left', text="Voltage (uV)")
        self.plot_zone_td0.setLabel(axis='bottom', text='Time')
        # self.plot_zone_td0.setXRange(0, 1, padding=0)
        self.plot_zone_td0.setYRange(-1000, 1000, padding=0)
        self.vbox_plots.addWidget(self.plot_zone_td0)

        self.plot_zone_td1 = pg.PlotWidget()
        self.plot_zone_td1.setMinimumWidth(500)
        self.plot_zone_td1.setTitle("Player 2")
        self.plot_zone_td1.setLabel(axis='left', text="Voltage (uV)")
        self.plot_zone_td1.setLabel(axis='bottom', text='Time')
        self.plot_zone_td1.setYRange(-1000, 1000, padding=0)
        self.vbox_plots.addWidget(self.plot_zone_td1)


        self.hbox0.addLayout(self.vbox_plots)

        self.button_grp = QtWidgets.QGroupBox()
        self.button_grp.setTitle("Controls")
        self.button_grp.setMaximumWidth(200)
        self.button_grp.setEnabled(True)
        self.hbox0.addWidget(self.button_grp)

        self.button_grp_vbox0 = QtWidgets.QVBoxLayout()
        self.button_grp.setLayout(self.button_grp_vbox0)

        self.plotButton = QtWidgets.QPushButton("Do Plot")
        self.plotButton.clicked.connect(self.draw_plot)
        self.button_grp_vbox0.addWidget(self.plotButton)

        self.calibrationButton = QtWidgets.QPushButton("Calibration")
        self.calibrationButton.setEnabled(False)
        self.button_grp_vbox0.addWidget(self.calibrationButton)

        self.gameButton = QtWidgets.QPushButton("Begin Game")
        self.gameButton.setCheckable(True)
        self.gameButton.setEnabled(False)
        if self.gameButton.isChecked() != True:
            self.gameButton.setStyleSheet("background-color: red")
        else:
            self.gameButton.setStyleSheet("background-color: green")
        self.button_grp_vbox0.addWidget(self.gameButton)

        self.info = QtWidgets.QLabel(f"Current State: {self._mode.value}")
        self.button_grp_vbox0.addWidget(self.info)
        self.button_grp_vbox0.addStretch()

        self.vbox0.addLayout(self.hbox0)

        self.cmd_display = QtWidgets.QTextEdit("ECE 202")
        self.cmd_display.setMaximumHeight(300)
        self.cmd_display.setReadOnly(True)

        self.vbox0.addWidget(self.cmd_display)

        self.rolling_data = []

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(TICK_INTERVAL*1000)

        self.calibration_timer = QtCore.QTimer()
        self.calibration_timer.timeout.connect(self.calibration_tick)
        self.calibrationButton.clicked.connect(partial(self.calibration_timer.start, 1000)) # Do not change from 1 second since calibration_tick times for user)

    def write_to_cmd(self, msg: str):
        previous_text = '\n'.join(self.cmd_display.toPlainText().split('\n')[-50:])
        self.cmd_display.setText(f"{previous_text}\n{msg}")
        self.cmd_display.verticalScrollBar().setValue(
            self.cmd_display.verticalScrollBar().maximum()
        )

    def add_to_selected_ports(self, double_clicked_port):
        if self.selected_ports.count() == 2:
            self.write_to_cmd("You may only select up to two ports.")
            return
        self.selected_ports.addItem(PortListWidgetItem(double_clicked_port.text()))
        self.available_ports.takeItem(self.available_ports.row(double_clicked_port))
        self.scommand.sendall(f"set {double_clicked_port.text().lower()}.tcpdataoutputenabled true".encode())
        self.write_to_cmd(f"Analog port: {double_clicked_port.text()} has been activated.")
        self.available_ports.sortItems()
        self.selected_ports.sortItems()
        if self.selected_ports.count() == 2:
            self.calibrationButton.setEnabled(True)
            self.scommand.sendall(b'set runmode run')
        time.sleep(SERVER_WAIT)


    def remove_from_selected_ports(self, double_clicked_port):
        self.available_ports.addItem(PortListWidgetItem(double_clicked_port.text()))
        self.selected_ports.takeItem(self.selected_ports.row(double_clicked_port))
        self.scommand.sendall(f"set {double_clicked_port.text().lower()}.tcpdataoutputenabled false".encode())
        self.write_to_cmd(f"Analog port: {double_clicked_port.text()} has been deactivated.")
        self.available_ports.sortItems()
        self.selected_ports.sortItems()
        if self.selected_ports.count() != 2:
            self.calibrationButton.setEnabled(False)
    
    def draw_plot(self):
        asdf = {
            "time": [0.01, 0.1, 1, 10, 100, 1000, 10000],
            "value": [5, 10, 20, 30, 20, 10, 0],
        }

        # plot data: x, y values
        # self.plot_zone_td1.setTitle("Power Spectral Density")
        # self.plot_zone_td1.setLabel(axis="left", text="Magnitude")
        # self.plot_zone_td1.setLabel(axis="bottom", text="Freq")
        # self.plot_zone_td1.getAxis("bottom").setLogMode(True)
        # self.plot_zone_td1.plot(
        #     asdf["time"], asdf["value"])

    def plot_time_domain_data(self):
        # [([0, 1, 2, 3], [s1, s1, s1], [s2, s2, s2]), ([0, 1, 2, 3], [s1, s1, s1], [s2, s2, s2]), ....]
        ts = [x[0] for x in self.rolling_data]  # [[0, 1, 2, 3], [0, 1, 2, 3], [0, 1, 2, 3]]
        samp0 = [x[1] for x in self.rolling_data]  # [[s1, s1, s1], [s1, s1, s1], ...]
        samp1 = [x[2] for x in self.rolling_data]
        ts = list(itertools.chain(*ts))
        samp0 = list(itertools.chain(*samp0))
        samp1 = list(itertools.chain(*samp1))

        # ts_all = list(ts[0])
        # for time_data in ts[1:]:
        #     ts_all.extend([x+ts_all[-1]+self.timestep for x in time_data])

        self.plot_zone_td0.clear()
        self.plot_zone_td1.clear()
        self.plot_zone_td0.plot(ts, samp0, pen=pg.mkPen(color='r'))
        self.plot_zone_td1.plot(ts, samp1, pen=pg.mkPen(color='b'))

    def plot_calibration_data(self):
        relax_data = list(zip(*self.calibration_data[StateMachineModes.CALIBRATE_P1_RELAX]))
        flex_data = list(zip(*self.calibration_data[StateMachineModes.CALIBRATE_P1_FLEX]))
        dbl_flex_data = list(zip(*self.calibration_data[StateMachineModes.CALIBRATE_P2_RELAX]))
        if relax_data:
            #self.plot_zone_td0.plot(relax_data[0], relax_data[1], pen=pg.mkPen(color='y'))
            self.plot_zone_td1.clear()
            self.plot_zone_td1.plot(np.abs(np.fft.fft(relax_data[1]))**2, pen=pg.mkPen(color='r'))
        if flex_data:
            self.plot_zone_td1.plot(np.abs(np.fft.fft(flex_data[1]))**2, pen=pg.mkPen(color='b'))
        if dbl_flex_data:
            self.plot_zone_td1.plot(np.abs(np.fft.fft(dbl_flex_data[1]))**2, pen=pg.mkPen(color='g'))

    def calibration_tick(self):
        self.calibrationButton.setEnabled(False)
        if self._mode == StateMachineModes.IDLE:
            self._mode = StateMachineModes.CALIBRATE_P1_RELAX
            self.write_to_cmd(f"Beginning calibration for {self._mode.value}.")
        if self._mode == StateMachineModes.CALIBRATE_P1_RELAX and self._tick_count == CALIBRATION_ELAPSED:
            self.write_to_cmd(f"Calibration for {self._mode.value} completed.")
            self.calibrate()
            self._mode = StateMachineModes.CALIBRATE_P1_FLEX
            self.write_to_cmd(f"Beginning calibration for {self._mode.value}.")
            self._tick_count = 0
        if self._mode == StateMachineModes.CALIBRATE_P1_FLEX and self._tick_count == CALIBRATION_ELAPSED:
            self.write_to_cmd(f"Calibration for {self._mode.value} completed.")
            self.calibrate()
            self._mode = StateMachineModes.CALIBRATE_P2_RELAX
            self.write_to_cmd(f"Beginning caibration for {self._mode.value}.")
            self._tick_count = 0
        if self._mode == StateMachineModes.CALIBRATE_P2_RELAX and self._tick_count == CALIBRATION_ELAPSED:
            self.write_to_cmd(f"Calibration for {self._mode.value} completed.")
            self.calibrate()
            self._mode=StateMachineModes.CALIBRATE_P2_FLEX
            self.write_to_cmd(f"Beginning calibration for {self._mode.value}.")
            self._tick_count = 0
        if self._mode == StateMachineModes.CALIBRATE_P2_FLEX and self._tick_count == CALIBRATION_ELAPSED:
            self.write_to_cmd(f"Calibration for {self._mode.value} completed.")
            self.calibrate()
            self.write_to_cmd("Calibration completed.")
            self._mode = StateMachineModes.IDLE
            self.calibrationButton.setEnabled(True)
            self.calibration_timer.stop()
            self.write_to_cmd(f"P1 Relax: {self.calibration_data[StateMachineModes.CALIBRATE_P1_RELAX]}")
            self.write_to_cmd(f"P1 Flex: {self.calibration_data[StateMachineModes.CALIBRATE_P1_FLEX]}")
            self.write_to_cmd(f"P2 Relax: {self.calibration_data[StateMachineModes.CALIBRATE_P2_RELAX]}")
            self.write_to_cmd(f"P2 Flex: {self.calibration_data[StateMachineModes.CALIBRATE_P2_FLEX]}")
            self._tick_count = 0
            return

        if self._tick_count != 0:
            self.write_to_cmd(f"{self._tick_count}...")
        self._tick_count = self._tick_count + 1
    
    # Last second of data for calibration
    def calibrate(self):
        
        samp0 = [x[1] for x in self.rolling_data[-10:]]
        samp1 = [x[2] for x in self.rolling_data[-10:]]
        samp0 = list(itertools.chain(*samp0))
        samp1 = list(itertools.chain(*samp1))
        samp0 = [abs(x) for x in samp0]
        samp1 = [abs(x) for x in samp1]
        if self._mode == StateMachineModes.CALIBRATE_P1_RELAX:
            self.calibration_data[StateMachineModes.CALIBRATE_P1_RELAX] = sum(samp0)/(2*10*TICK_INTERVAL)
        if self._mode == StateMachineModes.CALIBRATE_P1_FLEX:
            self.calibration_data[StateMachineModes.CALIBRATE_P1_FLEX] = (sum(samp1) - sum(samp0))/(2*10*TICK_INTERVAL)
        if self._mode == StateMachineModes.CALIBRATE_P2_RELAX:
            pass
        if self._mode == StateMachineModes.CALIBRATE_P2_FLEX:
            pass

    def tick(self):
        self.info.setText(f"Current State: {self._mode.value}")

        if self.selected_ports.count() != 2:
            self.scommand.sendall(b'get runmode')
            time.sleep(SERVER_WAIT)
            if (str(self.scommand.recv(COMMAND_BUFFER_SIZE), "utf-8") != "Return: RunMode Stop"):
                self.scommand.sendall(b'set runmode stop')
            self.gameButton.setEnabled(False)
            return

        self.gameButton.setEnabled(bool(self.calibration_data[StateMachineModes.CALIBRATE_P2_RELAX])) #Better check?

            # self.scommand.sendall(b'set runmode stop')
            # time.sleep(SERVER_WAIT)
        data = []
        raw_data = self.swaveform.recv(1028*16)
        for block_data in raw_data.split(struct.pack("<I", 0x2ef07a08))[1:]:
            # raw_sample[0] is the lowest selected channel
            for raw_timestamp, raw_samples0, raw_samples1 in struct.iter_unpack(f"<iHH", block_data):
                data.append(
                    (
                        raw_timestamp * self.timestep,
                        (raw_samples0 - 32768)*0.195,
                        (raw_samples1 - 32768)*0.195,
                    ),
                )
        ts, samp0, samp1 = zip(*data)
        self.rolling_data = self.rolling_data[-20:] + [(ts, samp0, samp1)]
        self.plot_time_domain_data()                
                #self.plot_zone_td1.plot(np.abs(np.fft.fft(samp0))**2, pen=pg.mkPen(color='m'))
                #self.plot_zone_td1.plot(np.abs(np.fft.fft(samp1))**2, pen=pg.mkPen(color='w'))
        # if self._tick_count * TICK_INTERVAL == CALIBRATION_ELAPSED:
                # self.plot_calibration_data()
    
def main():
    print('Connecting to TCP command server...')
    scommand = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while True:
        try:
            scommand.connect(('127.0.0.1', 5000))
        except ConnectionRefusedError:
            print("Connection to TCP command server unsucessful.\n Trying again...")
            time.sleep(1)
        else:
            break

    print('Connecting to TCP waveform server...')
    swaveform = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while True:
        try:
            swaveform.connect(('127.0.0.1', 5001))
        except ConnectionRefusedError:
            print("Connection to TCP waveform server unsuccessful.\n Trying again...")
            time.sleep(1)
        else:
            break
    
    scommand.sendall(b'get runmode')
    commandReturn = str(scommand.recv(COMMAND_BUFFER_SIZE), "utf-8")
    isStopped = commandReturn == "Return: RunMode Stop"

    if not isStopped:
        scommand.sendall(b'set runmode stop')
        time.sleep(SERVER_WAIT)

    scommand.sendall(b'get sampleratehertz')
    commandReturn = str(scommand.recv(COMMAND_BUFFER_SIZE), "utf-8")
    expectedReturnString = "Return: SampleRateHertz "
    if commandReturn.find(expectedReturnString) == -1: # Look for "Return: SampleRateHertz N" where N is the sample rate
        raise Exception('Unable to get sample rate from server')
    else:
        sampleRate = float(commandReturn[len(expectedReturnString):])

    timestep = 1 / sampleRate

    scommand.sendall(b"set notchfilterfreqhertz 60")
    time.sleep(SERVER_WAIT)

    scommand.sendall(b'execute clearalldataoutputs')
    time.sleep(SERVER_WAIT)


    app = QtWidgets.QApplication([])
    window = MainWindow(scommand, swaveform, timestep)
    window.show()
    app.exec()

    scommand.sendall(b'get runmode')
    commandReturn = str(scommand.recv(COMMAND_BUFFER_SIZE), "utf-8")
    isStopped = commandReturn == "Return: RunMode Stop"

    if not isStopped:
        scommand.sendall(b'set runmode stop')
        time.sleep(0.1)

if __name__ == '__main__':
    main()