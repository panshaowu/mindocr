import albumentations as alb
import numpy as np
from PIL import Image

import mindspore as ms
from mindspore.dataset import vision
from mindspore.dataset.vision.utils import Inter

IMAGENET_DEFAULT_MEAN = (0.485, 0.456, 0.406)
IMAGENET_DEFAULT_STD = (0.229, 0.224, 0.225)

INTERPOLATION = {
    "nearest": Inter.NEAREST,
    "antialias": Inter.ANTIALIAS,
    "linear": Inter.LINEAR,
    "cubic": Inter.PILCUBIC,
    "bicubic": Inter.BICUBIC,
}


def alb_wrapper(transform):
    def f(im):
        img = transform(image=np.asarray(im))["image"]
        img = np.transpose(img, (2, 0, 1))
        img = np.expand_dims(img, axis=0)
        return img

    return f


def load_image(image_file):
    image = Image.open(image_file).convert("RGB")
    return image


image_processor_high = alb_wrapper(
    alb.Compose(
        [
            alb.Resize(1024, 1024),
            alb.Normalize(IMAGENET_DEFAULT_MEAN, IMAGENET_DEFAULT_STD),
        ]
    )
)


class BCHW2BHWC:
    """
    Transform a batch of image from CHW to HWC.

    Args:
        image_batch (tensor, numpy.array, PIL.Image, list): for tensor or numpy input, the
        channel should be (bz, c, h, w) or (c, h, w). for list, the item should be
        PIL.Image or numpy.array (c, h, w).

    Return:
        transformed image batch: for numpy or tensor input, return a numpy array, the channel
        is (bz, h, w, c) or (h, w, c); for PIL.Image input, it is returned directly.
    """

    def __call__(self, image_batch):
        """the call function"""
        if isinstance(image_batch, ms.Tensor):
            image_batch = image_batch.asnumpy()

        if isinstance(image_batch, list):
            return [self(item) for item in image_batch]
        if isinstance(image_batch, np.ndarray):
            if len(image_batch.shape) == 4:
                return image_batch.transpose(0, 2, 3, 1)
            if len(image_batch.shape) == 3:
                return image_batch.transpose(1, 2, 0)
            raise ValueError(f"the rank of image_batch should be 3 or 4, but got {len(image_batch.shape)}")
        if isinstance(image_batch, Image.Image):
            return image_batch
        raise TypeError(f"the type {type(image_batch)} of image_batch is unsupported.")


class BatchPILize:
    """transform a batch of image to PIL.Image list."""

    def __call__(self, image_batch):
        """
        The forward process.

        Args:
            image_batch (tensor, numpy.array, list): for tensor or numpy input,
            the rank should be 4 or 3. for list, the item should be PIL.Image.

        Returns:
            return a tensor or a list of tensor.
        """
        if isinstance(image_batch, Image.Image):
            return image_batch

        if isinstance(image_batch, list):
            for item in image_batch:
                if not isinstance(item, Image.Image):
                    raise TypeError(
                        "unsupported type in list,"
                        " when the image_batch is a list,"
                        " the item in list should be PIL.Image."
                    )
            return image_batch

        if isinstance(image_batch, ms.Tensor):
            image_batch = image_batch.asnumpy()

        if isinstance(image_batch, np.ndarray):
            if len(image_batch.shape) == 4:
                return [Image.fromarray(item.astype(np.uint8)) for item in image_batch]
            if len(image_batch.shape) == 3:
                return Image.fromarray(image_batch.astype(np.uint8))
            raise ValueError(f"the rank of image_batch should be 3 or 4, but got {len(image_batch.shape)}")

        raise ValueError("unsupported input type.")


class BatchResize:
    """
    Resize a batch of image to the given shape.

    Args:
         image_resolution (int): the target size.
         interpolation: interpolate method, default is "cubic".
    """

    def __init__(self, image_resolution, interpolation="cubic"):
        self.interpolation = INTERPOLATION.get(interpolation)
        self.resize = vision.c_transforms.Resize(image_resolution, self.interpolation)

    def __call__(self, image_batch):
        """
        The forward process.

        Args:
            image_batch (tensor, numpy.array, PIL.Image, list): for tensor or numpy input,
            the shape should be (bz, h, w, c) or (h, w, c). for list, the item should be
            PIL.Image or numpy.array (h, w, c).

        Returns:
            resized image batch: for numpy or tensor input, return a numpy array;
            for PIL.Image input, it returns PIL.Image.
        """
        if isinstance(image_batch, ms.Tensor):
            image_batch = image_batch.asnumpy()

        if isinstance(image_batch, list):
            return [self.resize(item) for item in image_batch]
        if isinstance(image_batch, np.ndarray):
            if len(image_batch.shape) == 4:
                return np.row_stack([self.resize(item)[np.newaxis, :] for item in image_batch])
            if len(image_batch.shape) == 3:
                return self.resize(image_batch)
            raise ValueError(f"the rank of image_batch should be 3 or 4, but got {len(image_batch.shape)}")
        if isinstance(image_batch, Image.Image):
            return self.resize(image_batch)
        raise TypeError(f"the type {type(image_batch)} of image_batch is unsupported.")


class BatchCenterCrop:
    """
    CenterCrop a batch of image to the given shape.

    Args:
         image_resolution (int): the target size.
    """

    def __init__(self, image_resolution):
        self.crop = vision.CenterCrop(image_resolution)

    def __call__(self, image_batch):
        """
        The forward process.

        Args:
            image_batch (tensor, numpy.array, PIL.Image, list): for tensor or numpy input,
            the shape should be (bz, h, w, c) or (h, w, c). for list, the item should be
            PIL.Image or numpy.array (h, w, c).

        Returns:
            center cropped image batch: for numpy or tensor input, return a numpy array, the shape
            is (bz, image_resolution, image_resolution, c) or (image_resolution,
            image_resolution, c); for PIL.Image input, it is returned with shape (image_resolution,
            image_resolution).
        """
        if isinstance(image_batch, ms.Tensor):
            image_batch = image_batch.asnumpy()

        if isinstance(image_batch, list):
            return [self.crop(item) for item in image_batch]
        if isinstance(image_batch, np.ndarray):
            if len(image_batch.shape) == 4:
                return np.row_stack([self.crop(item)[np.newaxis, :] for item in image_batch])
            if len(image_batch.shape) == 3:
                return self.crop(image_batch)
            raise ValueError(f"the rank of image_batch should be 3 or 4, but got {len(image_batch.shape)}")
        if isinstance(image_batch, Image.Image):
            return self.crop(image_batch)
        raise TypeError(f"the type {type(image_batch)} of image_batch is unsupported.")


class BatchToTensor:
    """Transform a batch of image to tensor and scale to (0, 1)."""

    def __init__(self):
        self.totensor = ms.dataset.vision.ToTensor()

    def __call__(self, image_batch):
        """
        The forward process.

        Args:
            image_batch (tensor, numpy.array, PIL.Image, list): for tensor or numpy input,
            the rank should be 4 or 3. for list, the item should be PIL.Image or numpy.array.

        Returns:
            return a tensor or a list of tensor.
        """
        if isinstance(image_batch, ms.Tensor):
            image_batch = image_batch.asnumpy()

        if isinstance(image_batch, list):
            return [self.totensor(item) for item in image_batch]
        if isinstance(image_batch, np.ndarray):
            if len(image_batch.shape) == 4:
                return np.row_stack([self.totensor(item)[np.newaxis, :] for item in image_batch])
            if len(image_batch.shape) == 3:
                return self.totensor(image_batch)
            raise ValueError(f"the rank of image_batch should be 3 or 4, but got {len(image_batch.shape)}")
        if isinstance(image_batch, Image.Image):
            return self.totensor(image_batch)
        raise TypeError(f"the type {type(image_batch)} of image_batch is unsupported.")


class BatchNormalize:
    """Normalize a batch of image."""

    def __init__(
        self, mean=(0.48145466, 0.4578275, 0.40821073), std=(0.26862954, 0.26130258, 0.27577711), is_hwc=False
    ):
        self.normalize = vision.Normalize(mean=mean, std=std, is_hwc=is_hwc)

    def __call__(self, image_batch):
        """
        The forward process.

        Args:
            image_batch (tensor, numpy.array, list): for tensor or numpy input,
            the rank should be 4 or 3. for list, the item should be numpy.array.

        Returns:
            return a tensor or a list of tensor.
        """
        if isinstance(image_batch, ms.Tensor):
            image_batch = image_batch.asnumpy()

        if isinstance(image_batch, list):
            return [self.normalize(item) for item in image_batch]
        if isinstance(image_batch, np.ndarray):
            if len(image_batch.shape) == 3:
                return self.normalize(image_batch)
            if len(image_batch.shape) == 4:
                return np.row_stack([self.normalize(item)[np.newaxis, :] for item in image_batch])
            raise ValueError(f"the rank of image_batch should be 3 or 4, but got {len(image_batch.shape)}")
        raise TypeError(f"the type {type(image_batch)} of image_batch is unsupported.")


class VaryCLIPImageProcessor:
    def __init__(self, image_resolution=224):
        self.image_resolution = image_resolution
        self.bchw2bhwc = BCHW2BHWC()
        self.batch_pilizer = BatchPILize()
        self.batch_resizer = BatchResize(self.image_resolution)
        self.batch_crop = BatchCenterCrop(self.image_resolution)
        self.batch_totensor = BatchToTensor()
        self.batch_normalizer = BatchNormalize()

    def __call__(self, images):
        if not self._bhwc_check(images):
            images = self.bchw2bhwc(images)
        images = self.batch_pilizer(images)
        images = self.batch_resizer(images)
        images = self.batch_crop(images)
        images = self.batch_totensor(images)
        images = self.batch_normalizer(images)

        if isinstance(images, list):
            return np.row_stack([np.expand_dims(item, axis=0) for item in images])
        if len(images.shape) == 4:
            return images
        return np.expand_dims(images, axis=0)

    @staticmethod
    def _bhwc_check(image_batch):
        r"""Bhwc_check"""
        if isinstance(image_batch, np.ndarray):
            if image_batch.shape[-1] == 3:
                return True
        if isinstance(image_batch, ms.Tensor):
            if image_batch.asnumpy().shape[-1] == 3:
                return True
        if isinstance(image_batch, (list, Image.Image)):
            return True
        return False


class VarySAMImageProcessor:
    def __init__(self):
        self.image_processor_high = alb_wrapper(
            alb.Compose(
                [
                    alb.Resize(1024, 1024),
                    alb.Normalize(IMAGENET_DEFAULT_MEAN, IMAGENET_DEFAULT_STD),
                ]
            )
        )

    def __call__(self, images):
        images = self.image_processor_high(images)
        return images


class VaryImageProcessor:
    def __init__(self):
        self.sam_processor = VarySAMImageProcessor()
        self.clip_processor = VaryCLIPImageProcessor()

    def __call__(self, images):
        if isinstance(images, str):
            images = load_image(images)
        image_clip = self.clip_processor(images)
        image_sam = self.sam_processor(images)
        return image_clip, image_sam


class MonkeyImageProcessor:
    def __init__(self):
        self.resize1 = vision.c_transforms.Resize((896, 896), Inter.PILCUBIC)
        self.resize2 = vision.Resize((448, 448), Inter.BICUBIC)
        mean = (0.48145466, 0.4578275, 0.40821073)
        std = (0.26862954, 0.26130258, 0.27577711)
        self.normalize = vision.Normalize(mean=mean, std=std, is_hwc=False)

    @staticmethod
    def sliding_window(images, window_size=(448, 448), stride=448):
        windows = []
        for i in range(2):
            for j in range(2):
                window = images[
                    :, :, i * stride : i * stride + window_size[0], j * stride : j * stride + window_size[1]
                ]
                windows.append(window)
        return windows

    def __call__(self, images):
        if isinstance(images, str):
            images = load_image(images)
        images = self.resize1(images)  # hwc -> hwc
        images = images / 255.0  # hwc -> hwc
        images_trans = images.transpose(2, 0, 1)  # hwc -> chw
        images_norm = self.normalize(images_trans)  # chw -> chw
        images_nchw = np.expand_dims(images_norm, 0)  # chw -> nchw
        windows = self.sliding_window(images_nchw, window_size=(448, 448), stride=448)  # nchw -> List[nchw]
        images_norm = images_norm.transpose(1, 2, 0)
        images_448 = self.resize2(images_norm)  # hwc -> hwc
        images_448 = np.expand_dims(images_448.transpose(2, 0, 1), 0)  # hwc -> nchw
        return windows, images_448
