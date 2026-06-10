from pylcp_gui.dataframe.dataframe import LaserData


class LaserBeam:
    def __init__(self, laser_data: LaserData):
        freq, kvec, pol, intensity = (laser_data.freq, laser_data.kvec,
                                      laser_data.pol, laser_data.intensity)
        self.freq = freq
        self.kvec = kvec
        self.pol = pol
        self.intensity = intensity
