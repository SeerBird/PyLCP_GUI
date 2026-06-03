import numpy as np


def sort_float_then_string(numbers,strings):
    energy_label_pairs = np.asarray([(numbers[i], strings[i]) for i in range(len(numbers))],
                                    dtype=[('energy', float), ('label', 'S10')])
    return np.argsort(energy_label_pairs, order=['energy', 'label'])