import numpy as np
import os
from loguru import logger
import cv2
import typing
from findit import FindIt

from stagesepx import toolbox


class BaseHook(object):
    def __init__(self, overwrite: bool = None, *_, **__):
        # default: dict
        logger.debug(f'start initialing: {self.__class__.__name__} ...')
        self.result = dict()
        self.overwrite = bool(overwrite)

    def do(self, frame_id: int, frame: np.ndarray, *_, **__) -> typing.Optional[np.ndarray]:
        logger.debug(f'hook: {self.__class__.__name__}, frame id: {frame_id}')
        return


def change_origin(_func):
    def _wrap(self: BaseHook, frame_id: int, frame: np.ndarray, *args, **kwargs):
        res = _func(self, frame_id, frame, *args, **kwargs)
        if not self.overwrite:
            return frame
        if res is not None:
            logger.debug(f'origin frame has been changed by {self.__class__.__name__}')
            return res
        else:
            return frame

    return _wrap


class ExampleHook(BaseHook):
    """ this hook will help you write your own hook class """
    def __init__(self, *_, **__):
        """
        hook has two ways to affect the result of analysis

        1. add your result to self.result (or somewhere else), and get it by yourself after cut or classify
        2. use label 'overwrite'. by enabling this, hook will changing the origin frame
        """
        super().__init__(*_, **__)

        # add your code here

    @change_origin
    def do(self, frame_id: int, frame: np.ndarray, *_, **__) -> typing.Optional[np.ndarray]:
        super().do(frame_id, frame, *_, **__)

        # you can get frame_id and frame data here
        # and use them to custom your own function
        # add your code here

        # for example, i want to turn grey, and save size of each frames
        frame = toolbox.turn_grey(frame)
        self.result[frame_id] = frame.shape

        # if you are going to change the origin frame
        # just return the changed frame
        # and set 'overwrite' to 'True' when you are calling __init__
        return frame

        # for safety, if you do not want to modify the origin frame
        # you can return a 'None' instead of frame
        # and nothing will happen even if setting 'overwrite' to 'True'


class FrameSaveHook(BaseHook):
    """ add this hook, and save all the frames you want to specific dir """

    def __init__(self, target_dir: str, compress_rate: float = None, *_, **__):
        super().__init__(*_, **__)

        # init target dir
        self.target_dir = target_dir
        os.makedirs(target_dir, exist_ok=True)

        # compress rate
        self.compress_rate = compress_rate or 0.2

        logger.debug(f'target dir: {target_dir}')
        logger.debug(f'compress rate: {compress_rate}')

    @change_origin
    def do(self,
           frame_id: int,
           frame: np.ndarray,
           *_, **__) -> typing.Optional[np.ndarray]:
        super().do(frame_id, frame, *_, **__)
        compressed = toolbox.compress_frame(frame, compress_rate=self.compress_rate)
        target_path = os.path.join(self.target_dir, f'{frame_id}.png')
        cv2.imwrite(target_path, compressed)
        logger.debug(f'frame saved to {target_path}')
        return


class InvalidFrameDetectHook(BaseHook):
    def __init__(self,
                 compress_rate: float = None,
                 black_threshold: float = None,
                 white_threshold: float = None,
                 *_, **__):
        super().__init__(*_, **__)

        # compress rate
        self.compress_rate = compress_rate or 0.2

        # threshold
        self.black_threshold = black_threshold or 0.95
        self.white_threshold = white_threshold or 0.9

        logger.debug(f'compress rate: {compress_rate}')
        logger.debug(f'black threshold: {black_threshold}')
        logger.debug(f'white threshold: {white_threshold}')

    @change_origin
    def do(self,
           frame_id: int,
           frame: np.ndarray,
           *_, **__) -> typing.Optional[np.ndarray]:
        super().do(frame_id, frame, *_, **__)
        compressed = toolbox.compress_frame(frame, compress_rate=self.compress_rate)
        black = np.zeros([*compressed.shape, 3], np.uint8)
        white = black + 255
        black_ssim = toolbox.compare_ssim(black, compressed)
        white_ssim = toolbox.compare_ssim(white, compressed)
        logger.debug(f'black: {black_ssim}; white: {white_ssim}')

        self.result[frame_id] = {
            'black': black_ssim,
            'white': white_ssim,
        }
        return


class TemplateCompareHook(BaseHook):
    def __init__(self,
                 template_dict: typing.Dict[str, str],
                 *args, **kwargs):
        """
        args and kwargs will be sent to findit.__init__

        :param template_dict:
            # k: template name
            # v: template picture path
        :param args:
        :param kwargs:
        """
        super().__init__(*args, **kwargs)
        self.fi = FindIt(*args, **kwargs)
        self.template_dict = template_dict

    @change_origin
    def do(self,
           frame_id: int,
           frame: np.ndarray,
           *_, **__) -> typing.Optional[np.ndarray]:
        super().do(frame_id, frame, *_, **__)
        for each_template_name, each_template_path in self.template_dict.items():
            self.fi.load_template(each_template_name, each_template_path)
        res = self.fi.find(str(frame_id), target_pic_object=frame)
        logger.debug(f'compare with template {self.template_dict}: {res}')
        self.result[frame_id] = res
        return


class BinaryHook(BaseHook):
    @change_origin
    def do(self, frame_id: int, frame: np.ndarray, *_, **__) -> typing.Optional[np.ndarray]:
        # TODO not always work
        super().do(frame_id, frame, *_, **__)
        return toolbox.turn_binary(frame)
