import os
from typing import Sequence, Optional, Dict, Callable
from PIL import Image
import numpy as np
from torch.utils import data


class SegmentationList(data.Dataset):
    """A generic Dataset class for domain adaptation in image segmentation

    Parameters:
        - **root** (str): Root directory of dataset
        - **classes** (seq[str]): The names of all the classes
        - **data_list_file** (str): File to read the image list from.
        - **label_list_file** (str): File to read the label list from.
        - **data_folder** (str): Sub-directory of the image.
        - **label_folder** (str): Sub-directory of the label.
        - **mean** (seq[float]): mean BGR value. Normalize the image if not None. Default: None.
        - **id_to_train_id** (dict, optional): the map between the id on the label and the actual train id.
        - **train_id_to_color** (seq, optional): the map between the train id and the color.
        - **transforms** (callable, optional): A function/transform that  takes in  (PIL image, label) pair \
            and returns a transformed version. E.g, ``transforms.RandomCrop``.

    .. note:: In `data_list_file`, each line is the relative path of an image.
        If your data_list_file has different formats, please over-ride `parse_data_file`.
        ::
            source_dir/dog_xxx.png
            target_dir/dog_xxy.png

        In `label_list_file`, each line is the relative path of an label.
        If your label_list_file has different formats, please over-ride `parse_label_file`.
    """
    def __init__(self, root: str, classes: Sequence[str], data_list_file: str, label_list_file: str,
                 data_folder: str, label_folder: str, mean: Optional[Sequence[float]] = None,
                 id_to_train_id: Optional[Dict] = None, train_id_to_color: Optional[Sequence] = None,
                 transforms: Optional[Callable] = None):
        self.root = root
        self.classes = classes
        self.data_list_file = data_list_file
        self.label_list_file = label_list_file
        self.data_folder = data_folder
        self.label_folder = label_folder
        self.mean = mean
        self.ignore_label = 255
        self.id_to_train_id = id_to_train_id
        self.train_id_to_color = np.array(train_id_to_color)
        self.data_list = self.parse_data_file(self.data_list_file)
        self.label_list = self.parse_label_file(self.label_list_file)
        self.transforms = transforms

    def parse_data_file(self, file_name):
        """Parse file to image list
        Parameters:
            - **file_name** (str): The path of data file
            - **return** (list): List of image path
        """
        with open(file_name, "r") as f:
            data_list = [line.strip() for line in f.readlines()]
        return data_list

    def parse_label_file(self, file_name):
        """Parse file to label list
        Parameters:
            - **file_name** (str): The path of data file
            - **return** (list): List of label path
        """
        with open(file_name, "r") as f:
            label_list = [line.strip() for line in f.readlines()]
        return label_list

    def __len__(self):
        return len(self.data_list)

    def __getitem__(self, index):
        image_name = self.data_list[index]
        label_name = self.label_list[index]
        image = Image.open(os.path.join(self.root, self.data_folder, image_name)).convert('RGB')
        label = Image.open(os.path.join(self.root, self.label_folder, label_name))

        image, label = self.transforms(image, label)
        image = np.asarray(image, np.float32)
        label = np.asarray(label, np.int64)

        # remap label
        label_copy = self.ignore_label * np.ones(label.shape, dtype=np.int64)
        if self.id_to_train_id:
            for k, v in self.id_to_train_id.items():
                label_copy[label == k] = v

        # change to BGR
        image = image[:, :, ::-1]
        # normalize
        if self.mean is not None:
            image -= self.mean
        image = image.transpose((2, 0, 1))

        return image.copy(), label_copy.copy()

    @property
    def num_classes(self) -> int:
        """Number of classes"""
        return len(self.classes)

    def decode_input(self, image):
        """
        Recover the numpy array to PIL.Image

        Parameters:
            - **image** (np.array): normalized image in shape 3 x H x W
            - **return** (PIL.Image): RGB image in shape H x W x 3
        """
        image = image.transpose((1, 2, 0))
        image += self.mean
        image = image[:, :, ::-1]
        return Image.fromarray(image.astype(np.uint8))

    def decode_target(self, target):
        """ Decode label (each value is integer) into the corresponding RGB value.

        Parameters:
            - **target** (np.array): label in shape H x W
            - **return** (PIL.Image): RGB label in shape H x W x 3
        """
        target = target.copy()
        target[target == 255] = self.num_classes # unknown label is black on the RGB label
        target = self.train_id_to_color[target]
        return Image.fromarray(target.astype(np.uint8))

    def collect_image_paths(self):
        """Return a list of the absolute path of all the images"""
        return [os.path.join(self.root, self.data_folder, image_name) for image_name in self.data_list]