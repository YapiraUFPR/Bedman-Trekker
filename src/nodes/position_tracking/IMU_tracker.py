import numpy as np
from numpy.linalg import inv, norm
from mathlib import *

class IMUTracker:

    def __init__(self, sampling, data_order={'w': 1, 'a': 2, 'm': 3}):
        '''
        @param sampling: sampling rate of the IMU, in Hz
        @param tinit: initialization time where the device is expected to be stay still, in second
        @param data_order: specify the order of data in the data array
        '''

        super().__init__()
        # ---- parameters ----
        self.sampling = sampling
        self.dt = 1 / sampling    # second
        self.dts = self.dt**2   # second squared
        self.data_order = data_order

        # ---- helpers ----
        idx = {1: [0, 3], 2: [3, 6], 3: [6, 9]}
        self._widx = idx[data_order['w']]
        self._aidx = idx[data_order['a']]
        self._midx = idx[data_order['m']]

        self._p = np.array([[0, 0, 0]]).T
        self._prevt = -1
        self._t = 0

    def initialize(self, callib_data, noise_coefficient={'w': 100, 'a': 100, 'm': 10}):
        '''
        Algorithm initialization
        
        @param data: (,9) ndarray
        @param cut: cut the first few data to avoid potential corrupted data
        @param noise_coefficient: sensor noise is determined by variance magnitude times this coefficient
        
        Return: a list of initialization values used by EKF algorithm: 
        (gn, g0, mn, gyro_noise, gyro_bias, acc_noise, mag_noise)
        '''

        # discard the first few readings
        # for some reason they might fluctuate a lot
        data = callib_data[5:30]
        w = data[:, self._widx[0]:self._widx[1]]
        a = data[:, self._aidx[0]:self._aidx[1]]
        m = data[:, self._midx[0]:self._midx[1]]

        # ---- gravity ----
        gn = -a.mean(axis=0)
        gn = gn[:, np.newaxis]
        # save the initial magnitude of gravity
        g0 = np.linalg.norm(gn)

        # ---- magnetic field ----
        mn = m.mean(axis=0)
        # magnitude is not important
        mn = normalized(mn)[:, np.newaxis]

        # ---- compute noise covariance ----
        avar = a.var(axis=0)
        wvar = w.var(axis=0)
        mvar = m.var(axis=0)
        print('acc var: %s, norm: %s' % (avar, np.linalg.norm(avar)))
        print('ang var: %s, norm: %s' % (wvar, np.linalg.norm(wvar)))
        print('mag var: %s, norm: %s' % (mvar, np.linalg.norm(mvar)))

        # ---- define sensor noise ----
        gyro_noise = noise_coefficient['w'] * np.linalg.norm(wvar)
        gyro_bias = w.mean(axis=0)
        acc_noise = noise_coefficient['a'] * np.linalg.norm(avar)
        mag_noise = noise_coefficient['m'] * np.linalg.norm(mvar)

        self._init_list = (gn, g0, mn, gyro_noise, gyro_bias, acc_noise, mag_noise)
        self._an_drift_rate = self.calcAccErr(data)

    def attitudeTrack(self, data):
        '''
        Removes gravity from acceleration data and transform it into navitgaion frame.
        Also tracks device's orientation.
        
        @param data: (9) ndarray
        @param list: initialization values for EKF algorithm: 
        (gn, g0, mn, gyro_noise, gyro_bias, acc_noise, mag_noise)

        Return: (acc, orientation)
        '''

        # ------------------------------- #
        # ---- Initialization ----
        # ------------------------------- #
        gn, g0, mn, gyro_noise, gyro_bias, acc_noise, mag_noise = self._init_list
        w = data[self._widx[0]:self._widx[1]] - gyro_bias
        a = data[self._aidx[0]:self._aidx[1]]
        m = data[self._midx[0]:self._midx[1]]
        # sample_number = np.shape(data)[0]

        # ---- data container ----
        a_nav = []
        orix = []
        oriy = []
        oriz = []

        # ---- states and covariance matrix ----
        P = 1e-10 * I(4)    # state covariance matrix
        q = np.array([[1, 0, 0, 0]]).T    # quaternion state
        init_ori = I(3)   # initial orientation

        # ------------------------------- #
        # ---- Extended Kalman Filter ----
        # ------------------------------- #

        # all vectors are column vectors

        # t = 0
        # while t < sample_number:

        # ------------------------------- #
        # ---- 0. Data Preparation ----
        # ------------------------------- #

        wt = w[np.newaxis].T
        at = a[np.newaxis].T
        mt = normalized(m[np.newaxis].T)

        # ------------------------------- #
        # ---- 1. Propagation ----
        # ------------------------------- #

        Ft = F(q, wt, self.dt)
        Gt = G(q)
        Q = (gyro_noise * self.dt)**2 * Gt @ Gt.T

        q = normalized(Ft @ q)
        P = Ft @ P @ Ft.T + Q

        # ------------------------------- #
        # ---- 2. Measurement Update ----
        # ------------------------------- #

        # Use normalized measurements to reduce error!

        # ---- acc and mag prediction ----
        pa = normalized(-rotate(q) @ gn)
        pm = normalized(rotate(q) @ mn)

        # ---- residual ----
        Eps = np.vstack((normalized(at), mt)) - np.vstack((pa, pm))

        # ---- sensor noise ----
        # R = internal error + external error
        Ra = [(acc_noise / np.linalg.norm(at))**2 + (1 - g0 / np.linalg.norm(at))**2] * 3
        Rm = [mag_noise**2] * 3
        R = np.diag(Ra + Rm)

        # ---- kalman gain ----
        Ht = H(q, gn, mn)
        S = Ht @ P @ Ht.T + R
        K = P @ Ht.T @ np.linalg.inv(S)

        # ---- actual update ----
        q = q + K @ Eps
        P = P - K @ Ht @ P

        # ------------------------------- #
        # ---- 3. Post Correction ----
        # ------------------------------- #

        q = normalized(q)
        P = 0.5 * (P + P.T)    # make sure P is symmertical

        # ------------------------------- #
        # ---- 4. other things ----
        # ------------------------------- #

        # ---- navigation frame acceleration ----
        conj = -I(4)
        conj[0, 0] = 1
        an = rotate(conj @ q) @ at + gn

        # ---- navigation frame orientation ----
        orin = rotate(conj @ q) @ init_ori

        # ---- saving data ----
        a_nav = an.T[0]
        orix = orin.T[0, :]
        oriy = orin.T[1, :]
        oriz = orin.T[2, :]

        # t += 1

        return (a_nav, orix, oriy, oriz)
    
    def calcAccErr(self, data, threshold=0.2):
        '''
        Calculates drift in acc data assuming that
        the device stays still during initialization and ending period.
        The initial and final acc are inferred to be exactly 0.
        
        @param a_nav: acc data, raw output from the kalman filter
        @param threshold: acc threshold to detect the starting and ending point of motion
        
        Return: drift vector
        '''

        a_nav = []
        for d in data:
            a_nav.append(self.attitudeTrack(d)[0])
        a_nav = np.array(a_nav)

        sample_number = np.shape(a_nav)[0]
        t_start = 0
        for t in range(sample_number):
            at = a_nav[t]
            if np.linalg.norm(at) > threshold:
                t_start = t
                break

        t_end = 0
        for t in range(sample_number - 1, -1, -1):
            at = a_nav[t]
            if np.linalg.norm(at - a_nav[-1]) > threshold:
                t_end = t
                break

        an_drift = a_nav[t_end:].mean(axis=0)
        an_drift_rate = an_drift / (t_end - t_start)
        return an_drift_rate
    
    def removeAccErr(self, a_nav, threshold=0.2, filter=False, wn=(0.01, 15)):
        '''
        Removes drift in acc data assuming that
        the device stays still during initialization and ending period.
        The initial and final acc are inferred to be exactly 0.
        The final acc data output is passed through a bandpass filter to further reduce noise and drift.
        
        @param a_nav: acc data, raw output from the kalman filter
        @param threshold: acc threshold to detect the starting and ending point of motion
        @param wn: bandpass filter cutoff frequencies
        
        Return: corrected and filtered acc data
        '''

        sample_number = np.shape(a_nav)[0]
        t_start = 0
        for t in range(sample_number):
            at = a_nav[t]
            if np.linalg.norm(at) > threshold:
                t_start = t
                break

        t_end = 0
        for t in range(sample_number - 1, -1, -1):
            at = a_nav[t]
            if np.linalg.norm(at - a_nav[-1]) > threshold:
                t_end = t
                break

        an_drift = a_nav[t_end:].mean(axis=0)
        an_drift_rate = an_drift / (t_end - t_start)

        for i in range(t_end - t_start):
            a_nav[t_start + i] -= (i + 1) * an_drift_rate

        for i in range(sample_number - t_end):
            a_nav[t_end + i] -= an_drift

        if filter:
            filtered_a_nav = filtSignal([a_nav], dt=self.dt, wn=wn, btype='bandpass')[0]
            return filtered_a_nav
        else:
            return a_nav

    def zupt(self, a_nav, threshold):
        '''
        Applies Zero Velocity Update(ZUPT) algorithm to acc data.
        
        @param a_nav: acc data
        @param threshold: stationary detection threshold, the more intense the movement is the higher this should be

        Return: velocity data
        '''

        # sample_number = np.shape(a_nav)[0]
        # velocities = []
        # prevt = -1
        still_phase = False

        v = np.zeros((3, 1))
        # t = 0
        # while t < sample_number:
        at = a_nav[np.newaxis].T

        if np.linalg.norm(at) < threshold:
            if not still_phase:
                predict_v = v + at * self.dt

                v_drift_rate = predict_v / (self._t - self._prevt)
                # for i in range(self._t - self._prevt - 1):
                v -= v_drift_rate.T[0]

            v = np.zeros((3, 1))
            self._prevt = self._t
            still_phase = True
        else:
            v = v + at * self.dt
            still_phase = False

        # velocities.append(v.T[0])
            # t += 1

        # velocities = np.array(velocities)
        return v.T[0]

    def positionTrack(self, a_nav):
        '''
        Simple integration of acc data and velocity data.
        
        @param a_nav: acc data
        @param velocities: velocity data
        
        Return: 3D coordinates in navigation frame

        Modfied to store the previous iteration's position and add the current velocity to it
        '''

        # sample_number = np.shape(a_nav)[0]
        # positions = []

        # t = 0
        # while t < sample_number:
        at = a_nav[np.newaxis].T
        # vt = velocities[np.newaxis].T

        # self._p = self._p + vt * self.dt + 0.5 * at * self.dt**2
        self._p = self._p + at * self.dts
        # positions.append(self._p.T[0])
        # t += 1

        # positions = np.array(positions)
        # return positions
        return self._p.T[0]
    
    def calculatePosition(self, data):
        # EKF step
        a_nav, orix, oriy, oriz = self.attitudeTrack(data)
        # filtered_a_nav = filtSignal([a_nav], dt=self.dt, wn=5, btype='highpass')[0]
        # filtered_a_nav = a_nav
        return self.positionTrack(a_nav)