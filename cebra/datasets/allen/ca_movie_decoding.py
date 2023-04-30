"""Allen pseudomouse Ca decoding dataset with train/test split. 

References:
    *Deitch, Daniel, Alon Rubin, and Yaniv Ziv. "Representational drift in the mouse visual cortex." Current biology 31.19 (2021): 4327-4339.
    *de Vries, Saskia EJ, et al. "A large-scale standardized physiological survey reveals functional organization of the mouse visual cortex." Nature neuroscience 23.1 (2020): 138-151.
    *https://github.com/zivlab/visual_drift
    *http://observatory.brain-map.org/visualcoding

"""

import glob
import hashlib
import os

import h5py
import joblib
import numpy as np
import pandas as pd
import scipy.io
import torch
from numpy.random import Generator
from numpy.random import PCG64
from sklearn.decomposition import PCA

import cebra.data
from cebra.datasets import get_datapath
from cebra.datasets import parametrize
from cebra.datasets import register
from cebra.datasets.allen import NUM_NEURONS
from cebra.datasets.allen import SEEDS
from cebra.datasets.allen import SEEDS_DISJOINT


@parametrize(
    num_neurons=NUM_NEURONS,
    test_repeat=[10],
class AllenCaMoviesDataset(cebra.data.SingleSessionDataset):
    """A pseudomouse 30Hz calcium events dataset during the allen MOVIE1 stimulus with train/test splits.

    A dataset of stacked 30Hz calcium events from the excitatory neurons in the visual cortices (VISp, VISpm, VISam, VISrl, VISal, VISl) of multiple mice
    The continuous labels corresponding to a DINO embedding of each stimulus frame.
    The 10th repeat is held-out as a test set and the remaining 9 repeats consists a train set.

    Args:
        num_neurons: The number of neurons to sample. Choose from 10, 30, 50, 100, 200, 400, 600, 800, 900, 1000.
        seed: The random seeds for sampling neurons.
        preload: The path to the preloaded neural data. If `None`, the neural data is constructed from the source. Default value is `None`.
    """

        super().__init__()
        self.num_neurons = num_neurons
        self.seed = seed
        self.split_flag = split_flag
        self.test_repeat = test_repeat
        frame_feature = self._get_video_features(num_movie)
        if preload is None:
            pseudo_mice = self._get_pseudo_mice(cortex, num_movie)
            self.movie_len = int(pseudo_mice.shape[1] / 10)
            self.neurons_indices = self._sample_neurons(pseudo_mice)
            self._split(pseudo_mice, frame_feature)
        else:
            data = joblib.load(preload)
            self.neural = data["neural"]
                self.index = frame_feature.repeat(9, 1)
            else:
                self.index = frame_feature.repeat(1, 1)

        """Return behavior labels.

        The frame feature used as the behavior labels are returned.

        Args:
            num_movie: The number of the moive used as the stimulus. It is fixed to 'one'.
        """

        frame_feature_path = get_datapath(
            f"allen/features/allen_movies/vit_base/8/movie_{num_movie}_image_stack.npz/testfeat.pth"
        )
        frame_feature = torch.load(frame_feature_path)
        return frame_feature

    def _sample_neurons(self, pseudo_mice):
        """Randomly sample the specified number of neurons.
        The random sampling of the neurons specified by the `seed` and `num_neurons`.
        Args:
            pseudo_mice: The pseudomouse data.

        """

        sampler = Generator(PCG64(self.seed))
        neurons_indices = sampler.choice(np.arange(pseudo_mice.shape[0]),
                                         size=self.num_neurons)
        return neurons_indices

    def _split(self, pseudo_mice, frame_feature):
        """Split the dataset into train and test set.
        The first 9 repeats are train set and the last repeat is test set.
        Args:
            pseudo_mice: The pseudomouse neural data.
            frame_feature: The behavior labels.

        """

            self.index = frame_feature.repeat(9, 1)
            neural = pseudo_mice[self.neurons_indices, (self.test_repeat - 1) *
                                 self.movie_len:self.test_repeat *
            self.index = frame_feature.repeat(1, 1)
        else:
            raise ValueError("split_flag should be either train or test")

        self.neural = torch.from_numpy(neural.T).float()

    def _get_pseudo_mice(self, area, num_movie):
        """Construct pseudomouse neural dataset.

        Stack the excitatory neurons from the multiple mice and construct a psuedomouse neural dataset of the specified visual cortical area.
        The neurons which were recorded in all of the sessions A, B, C are included.

        Args:
            area: The visual cortical area to sample the neurons. Possible options: VISp, VISpm, VISam, VISal, VISl, VISrl.

        """

        list_mice = glob.glob(
            get_datapath(
                f"allen/visual_drift/data/calcium_excitatory/{area}/*"))
        exp_containers = [
            int(mice.split(f"{area}/")[1].replace(".mat", ""))
            for mice in list_mice
        ]
        ## Load summary file
        summary = pd.read_csv(get_datapath("allen/data_summary.csv"))
        ## Filter excitatory neurons in V1
        area_filtered = summary[(summary["exp"].isin(exp_containers)) &
                                (summary["target"] == area) &
                                ~(summary["cre_line"].str.contains("SSt")) &
                                ~(summary["cre_line"].str.contains("Pvalb")) &
                                ~(summary["cre_line"].str.contains("Vip"))]

        def _convert_to_nums(string):
            return list(
                map(
                    int,
                    string.replace("\n", "").replace("[",
                                                     "").replace("]",
                                                                 "").split(),
                ))

        ## Pseudo V1
        pseudo_mouse = []
        for exp_container in set(area_filtered["exp"]):
            neurons = summary[summary["exp"] == exp_container]["neurons"]
            sessions = summary[summary["exp"] == exp_container]["session_type"]
            seq_sessions = np.array(list(sessions)).argsort()
            common_neurons = set.intersection(
                set(_convert_to_nums(neurons.iloc[0])),
                set(_convert_to_nums(neurons.iloc[1])),
                set(_convert_to_nums(neurons.iloc[2])),
            )
            indices1 = [
                _convert_to_nums(neurons.iloc[0]).index(x)
                for x in common_neurons
            ]
            indices2 = [
                _convert_to_nums(neurons.iloc[1]).index(x)
                for x in common_neurons
            ]
            indices3 = [
                _convert_to_nums(neurons.iloc[2]).index(x)
                for x in common_neurons
            ]
            indices1.sort()
            indices2.sort()
            indices3.sort()
            indices = [indices1, indices2, indices3]
                f"allen/visual_drift/data/calcium_excitatory/{area}/{exp_container}.mat"
            traces = scipy.io.loadmat(matfile)
            for n, i in enumerate(seq_sessions):
                session = traces["filtered_traces_days_events"][n, 0][
                    indices[i], :]
                pseudo_mouse.append(session)

        pseudo_mouse = np.concatenate(pseudo_mouse)

        return pseudo_mouse

        pseudo_mouse = np.vstack(
            [get_neural_data(num_movie, mice) for mice in list_mice])

        return pseudo_mouse

    def __len__(self):
        return self.neural.size(0)

    @property
    def continuous_index(self):
        return self.index

    @property
    def input_dimension(self):
        return self.neural.size(1)

    def __getitem__(self, index):
        index = self.expand_index(index)

        return self.neural[index].transpose(2, 1)


@parametrize(
    num_neurons=[400],
    test_repeat=[10],
    seed=SEEDS_DISJOINT,
class AllenCaMoviesDisjointDataset(AllenCaMoviesDataset,
                                   cebra.data.SingleSessionDataset):
    """A disjoint pseudomouse 30Hz calcium events dataset of  during the allen MOVIE1 stimulus with train/test splits.

    A dataset of stacked 30Hz calcium events from the excitatory neurons in the visual cortices (VISp, VISpm, VISam, VISrl, VISal, VISl) of multiple mice
    The continuous labels corresponding to a DINO embedding of each stimulus frame.

    Args:
        seed: The random seeds for sampling neurons.

    """

    def __init__(self, num_movie, cortex, group, num_neurons, split_flag, seed,
                 test_repeat):
        super(AllenCaMoviesDataset, self).__init__()
        self.num_neurons = num_neurons
        self.seed = seed
        self.split_flag = split_flag
        self.test_repeat = test_repeat
        self.group = group
        frame_feature = self._get_video_features(num_movie)
        pseudo_mice = self._get_pseudo_mice(cortex, num_movie)
        self.movie_len = int(pseudo_mice.shape[1] / 10)
        self.neurons_indices = self._sample_neurons(pseudo_mice)
        self._split(pseudo_mice, frame_feature)

    def _sample_neurons(self, pseudo_mice):
        The sampled two groups of 400 neurons are non-overlapping.
        Args:
            pseudo_mice: The pseudomouse dataset.

        """

        sampler = Generator(PCG64(self.seed))
        permuted_neurons = sampler.permutation(pseudo_mice.shape[0])
        return np.array_split(permuted_neurons,
                              2)[self.group][:self.num_neurons]

    def _get_pseudo_mice(self, area, num_movie):
        """Construct pseudomouse neural dataset.

        Stack the excitatory neurons from the multiple mice and construct a psuedomouse neural dataset of the specified visual cortical area.
        The neurons recorded in session A are used.

        Args:
            area: The visual cortical area to sample the neurons. Possible options: VISp, VISpm, VISam, VISal, VISl, VISrl.

        """

        list_mice = glob.glob(
            get_datapath(
                f"allen/visual_drift/data/calcium_excitatory/{area}/*"))

        def _get_neural_data(num_movie, mat_file):
            mat = scipy.io.loadmat(mat_file)
                mat_index = None
                mat_index = (2, 1)
                mat_index = (0, 1)
            else:

            if mat_index is not None:
                events = mat[mat_key][mat_index[0], mat_index[1]]
            else:
                events = mat[mat_key][:, :, 0]  ## Take one session only

            return events

        pseudo_mouse = np.vstack(
            [_get_neural_data(num_movie, mice) for mice in list_mice])

        return pseudo_mouse