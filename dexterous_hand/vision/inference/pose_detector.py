"""姿态检测器模块.

支持三种推理后端：PyTorch、ONNX Runtime、CANN ACL。
自动选择最优后端，提供统一的检测接口。

Usage:
    python pose_detector.py --model best.pt --backend auto
"""

import argparse
import logging
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class Backend(Enum):
    """推理后端类型."""
    PYTORCH = "pytorch"
    ONNX = "onnx"
    CANN = "cann"
    AUTO = "auto"


@dataclass
class DetectionResult:
    """检测结果数据类."""
    bbox: np.ndarray  # [x1, y1, x2, y2]
    keypoints_21: np.ndarray  # [21, 3] (x, y, confidence)
    confidence: float  # 检测置信度


@dataclass
class LetterboxInfo:
    """Letterbox 变换信息."""
    new_shape: Tuple[int, int]
    dw: float
    dh: float
    ratio: float
    pad_color: Tuple[int, int, int] = (114, 114, 114)


class PoseDetector:
    """姿态检测器类.

    支持三种推理后端：PyTorch、ONNX Runtime、CANN ACL。
    自动选择最优后端，提供统一的检测接口。

    Attributes:
        model_path: 模型文件路径
        backend: 推理后端类型
        conf_threshold: 置信度阈值
        iou_threshold: NMS IoU 阈值
        imgsz: 输入图片尺寸
    """

    def __init__(
        self,
        model_path: str,
        backend: Union[str, Backend] = Backend.AUTO,
        conf_threshold: float = 0.5,
        iou_threshold: float = 0.45,
        imgsz: int = 640,
    ) -> None:
        """初始化姿态检测器.

        Args:
            model_path: 模型文件路径（支持 .pt, .onnx, .om）
            backend: 推理后端类型，可选 'auto', 'pytorch', 'onnx', 'cann'
            conf_threshold: 置信度阈值
            iou_threshold: NMS IoU 阈值
            imgsz: 输入图片尺寸
        """
        self.model_path = Path(model_path)
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.imgsz = imgsz

        # 解析后端类型
        if isinstance(backend, str):
            backend = Backend(backend.lower())
        self.backend = backend

        # 模型和会话
        self._model = None
        self._session = None
        self._input_name = None
        self._output_names = None

        # 初始化模型
        self._init_model()

    def _detect_backend(self) -> Backend:
        """自动检测可用的推理后端.

        Returns:
            Backend: 检测到的后端类型

        Raises:
            RuntimeError: 没有可用的后端
        """
        # 根据模型文件扩展名优先选择
        suffix = self.model_path.suffix.lower()

        if suffix == ".om":
            # OM 模型只能用 CANN
            if self._check_cann_available():
                return Backend.CANN
            else:
                raise RuntimeError("OM 模型需要 CANN 后端，但 CANN 不可用")

        if suffix == ".onnx":
            # ONNX 模型优先用 ONNX Runtime
            if self._check_onnx_available():
                return Backend.ONNX
            elif self._check_pytorch_available():
                return Backend.PYTORCH
            else:
                raise RuntimeError("没有可用的推理后端")

        if suffix == ".pt":
            # PyTorch 模型优先用 PyTorch
            if self._check_pytorch_available():
                return Backend.PYTORCH
            elif self._check_onnx_available():
                return Backend.ONNX
            else:
                raise RuntimeError("没有可用的推理后端")

        # 默认优先级：CANN > ONNX > PyTorch
        if self._check_cann_available():
            return Backend.CANN
        elif self._check_onnx_available():
            return Backend.ONNX
        elif self._check_pytorch_available():
            return Backend.PYTORCH
        else:
            raise RuntimeError("没有可用的推理后端")

    def _check_pytorch_available(self) -> bool:
        """检查 PyTorch 后端是否可用.

        Returns:
            bool: 是否可用
        """
        try:
            import torch
            from ultralytics import YOLO
            return True
        except ImportError:
            return False

    def _check_onnx_available(self) -> bool:
        """检查 ONNX Runtime 后端是否可用.

        Returns:
            bool: 是否可用
        """
        try:
            import onnxruntime as ort
            return True
        except ImportError:
            return False

    def _check_cann_available(self) -> bool:
        """检查 CANN ACL 后端是否可用.

        Returns:
            bool: 是否可用
        """
        try:
            import acl
            return True
        except ImportError:
            return False

    def _init_model(self) -> None:
        """初始化模型."""
        # 自动选择后端
        if self.backend == Backend.AUTO:
            self.backend = self._detect_backend()

        logger.info(f"使用推理后端: {self.backend.value}")
        logger.info(f"模型路径: {self.model_path}")

        # 根据后端初始化
        if self.backend == Backend.PYTORCH:
            self._init_pytorch()
        elif self.backend == Backend.ONNX:
            self._init_onnx()
        elif self.backend == Backend.CANN:
            self._init_cann()
        else:
            raise ValueError(f"不支持的后端类型: {self.backend}")

    def _init_pytorch(self) -> None:
        """初始化 PyTorch 后端."""
        from ultralytics import YOLO

        if not self.model_path.exists():
            raise FileNotFoundError(f"模型文件不存在: {self.model_path}")

        self._model = YOLO(str(self.model_path))
        logger.info("PyTorch 模型加载成功")

    def _init_onnx(self) -> None:
        """初始化 ONNX Runtime 后端."""
        import onnxruntime as ort

        if not self.model_path.exists():
            raise FileNotFoundError(f"模型文件不存在: {self.model_path}")

        # 创建推理会话
        session_options = ort.SessionOptions()
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        session_options.intra_op_num_threads = 4

        # 优先使用 GPU
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        self._session = ort.InferenceSession(
            str(self.model_path),
            sess_options=session_options,
            providers=providers,
        )

        # 获取输入输出名称
        self._input_name = self._session.get_inputs()[0].name
        self._output_names = [output.name for output in self._session.get_outputs()]

        logger.info("ONNX Runtime 模型加载成功")
        logger.info(f"  输入: {self._input_name}")
        logger.info(f"  输出: {self._output_names}")

    def _init_cann(self) -> None:
        """初始化 CANN ACL 后端."""
        import acl

        if not self.model_path.exists():
            raise FileNotFoundError(f"模型文件不存在: {self.model_path}")

        # 初始化 ACL
        ret = acl.init()
        if ret != 0:
            raise RuntimeError(f"ACL 初始化失败: {ret}")

        # 获取运行资源
        self._acl_config = acl.aclConfigCreate()
        self._acl_context = acl.aclContextCreate(self._acl_config)

        # 加载模型
        self._model_id, ret = acl.mdlLoadFromFile(str(self.model_path))
        if ret != 0:
            raise RuntimeError(f"模型加载失败: {ret}")

        # 获取模型描述
        self._model_desc = acl.mdlCreateDesc()
        ret = acl.mdlGetDesc(self._model_desc, self._model_id)
        if ret != 0:
            raise RuntimeError(f"获取模型描述失败: {ret}")

        # 获取输入输出信息
        input_count = acl.mdlGetNumInputs(self._model_desc)
        output_count = acl.mdlGetNumOutputs(self._model_desc)

        logger.info("CANN ACL 模型加载成功")
        logger.info(f"  输入数量: {input_count}")
        logger.info(f"  输出数量: {output_count}")

    def letterbox(
        self,
        image: np.ndarray,
        new_shape: Tuple[int, int] = (640, 640),
        color: Tuple[int, int, int] = (114, 114, 114),
    ) -> Tuple[np.ndarray, LetterboxInfo]:
        """Letterbox 图像缩放（保持宽高比）.

        Args:
            image: 输入图像
            new_shape: 目标尺寸 (height, width)
            color: 填充颜色

        Returns:
            Tuple[np.ndarray, LetterboxInfo]: 缩放后的图像和变换信息
        """
        shape = image.shape[:2]  # [height, width]

        if isinstance(new_shape, int):
            new_shape = (new_shape, new_shape)

        # 计算缩放比例
        r = min(new_shape[0] / shape[0], new_shape[1] / shape[1])

        # 计算填充
        new_unpad = int(round(shape[1] * r)), int(round(shape[0] * r))
        dw = (new_shape[1] - new_unpad[0]) / 2
        dh = (new_shape[0] - new_unpad[1]) / 2

        # 缩放图像
        if shape[::-1] != new_unpad:
            image = cv2.resize(image, new_unpad, interpolation=cv2.INTER_LINEAR)

        # 添加边框
        top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
        left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
        image = cv2.copyMakeBorder(
            image, top, bottom, left, right,
            cv2.BORDER_CONSTANT, value=color
        )

        info = LetterboxInfo(
            new_shape=new_shape,
            dw=dw,
            dh=dh,
            ratio=r,
            pad_color=color,
        )

        return image, info

    def preprocess(self, image: np.ndarray) -> Tuple[np.ndarray, LetterboxInfo]:
        """图像预处理.

        Args:
            image: 输入图像 (BGR)

        Returns:
            Tuple[np.ndarray, LetterboxInfo]: 预处理后的图像和变换信息
        """
        # Letterbox 缩放
        img, info = self.letterbox(image, (self.imgsz, self.imgsz))

        # BGR -> RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # 归一化
        img = img.astype(np.float32) / 255.0

        # HWC -> CHW
        img = np.transpose(img, (2, 0, 1))

        # 添加 batch 维度
        img = np.expand_dims(img, axis=0)

        # 确保内存连续
        img = np.ascontiguousarray(img)

        return img, info

    def postprocess(
        self,
        outputs: List[np.ndarray],
        letterbox_info: LetterboxInfo,
        original_shape: Tuple[int, int],
    ) -> List[DetectionResult]:
        """后处理模型输出.

        Args:
            outputs: 模型输出列表
            letterbox_info: Letterbox 变换信息
            original_shape: 原始图像尺寸 (height, width)

        Returns:
            List[DetectionResult]: 检测结果列表
        """
        # YOLOv8-pose 输出格式: [batch, 56, num_detections]
        # 56 = 4(bbox) + 1(conf) + 1(class) + 21*2(keypoints_x, keypoints_y)
        # 实际输出可能是 [batch, 56, 8400] 或类似格式

        predictions = outputs[0]  # [batch, 56, num_detections]

        if len(predictions.shape) == 3:
            predictions = predictions[0]  # [56, num_detections]

        # 转置为 [num_detections, 56]
        predictions = predictions.T

        # 分离各部分
        boxes = predictions[:, :4]  # [cx, cy, w, h]
        confidences = predictions[:, 4]
        classes = predictions[:, 5]
        keypoints = predictions[:, 6:]  # [21*2]

        # 置信度过滤
        mask = confidences >= self.conf_threshold
        boxes = boxes[mask]
        confidences = confidences[mask]
        keypoints = keypoints[mask]

        if len(boxes) == 0:
            return []

        # NMS
        # 将 cx, cy, w, h 转换为 x1, y1, x2, y2
        x1 = boxes[:, 0] - boxes[:, 2] / 2
        y1 = boxes[:, 1] - boxes[:, 3] / 2
        x2 = boxes[:, 0] + boxes[:, 2] / 2
        y2 = boxes[:, 1] + boxes[:, 3] / 2
        boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1)

        # 执行 NMS
        indices = self._nms(boxes_xyxy, confidences, self.iou_threshold)

        results = []
        for idx in indices:
            # 获取 bbox 并还原到原图坐标
            box = boxes_xyxy[idx].copy()
            box[0] = (box[0] - letterbox_info.dw) / letterbox_info.ratio
            box[1] = (box[1] - letterbox_info.dh) / letterbox_info.ratio
            box[2] = (box[2] - letterbox_info.dw) / letterbox_info.ratio
            box[3] = (box[3] - letterbox_info.dh) / letterbox_info.ratio

            # 裁剪到图像范围
            box[0] = max(0, min(box[0], original_shape[1]))
            box[1] = max(0, min(box[1], original_shape[0]))
            box[2] = max(0, min(box[2], original_shape[1]))
            box[3] = max(0, min(box[3], original_shape[0]))

            # 获取关键点并还原到原图坐标
            kpts = keypoints[idx].reshape(21, 2)
            kpts_x = (kpts[:, 0] - letterbox_info.dw) / letterbox_info.ratio
            kpts_y = (kpts[:, 1] - letterbox_info.dh) / letterbox_info.ratio

            # 添加置信度（使用检测置信度）
            kpts_conf = np.full((21, 1), confidences[idx])
            kpts_21 = np.stack([kpts_x, kpts_y, kpts_conf[:, 0]], axis=1)

            results.append(DetectionResult(
                bbox=box,
                keypoints_21=kpts_21,
                confidence=float(confidences[idx]),
            ))

        return results

    def _nms(
        self,
        boxes: np.ndarray,
        scores: np.ndarray,
        iou_threshold: float,
    ) -> List[int]:
        """非极大值抑制.

        Args:
            boxes: 边界框 [N, 4] (x1, y1, x2, y2)
            scores: 置信度 [N]
            iou_threshold: IoU 阈值

        Returns:
            List[int]: 保留的索引
        """
        x1 = boxes[:, 0]
        y1 = boxes[:, 1]
        x2 = boxes[:, 2]
        y2 = boxes[:, 3]

        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]

        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)

            if order.size == 1:
                break

            # 计算 IoU
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            intersection = w * h
            union = areas[i] + areas[order[1:]] - intersection
            iou = intersection / (union + 1e-6)

            # 保留 IoU 小于阈值的
            inds = np.where(iou <= iou_threshold)[0]
            order = order[inds + 1]

        return keep

    def _run_pytorch(self, preprocessed: np.ndarray) -> List[np.ndarray]:
        """使用 PyTorch 后端推理.

        Args:
            preprocessed: 预处理后的图像

        Returns:
            List[np.ndarray]: 模型输出
        """
        import torch

        # 获取原始图像（需要从预处理后的数据恢复）
        # 注意：这里需要传入原始图像，而不是预处理后的
        # 实际使用时会在 detect 方法中处理
        raise NotImplementedError("PyTorch 后端需要直接调用 YOLO API")

    def _run_onnx(self, preprocessed: np.ndarray) -> List[np.ndarray]:
        """使用 ONNX Runtime 后端推理.

        Args:
            preprocessed: 预处理后的图像

        Returns:
            List[np.ndarray]: 模型输出
        """
        outputs = self._session.run(
            self._output_names,
            {self._input_name: preprocessed},
        )
        return outputs

    def _run_cann(self, preprocessed: np.ndarray) -> List[np.ndarray]:
        """使用 CANN ACL 后端推理.

        Args:
            preprocessed: 预处理后的图像

        Returns:
            List[np.ndarray]: 模型输出
        """
        import acl

        # 准备输入数据
        input_data = preprocessed.astype(np.float32)

        # 创建输入数据缓冲区
        input_size = input_data.nbytes
        input_ptr, ret = acl.rt.malloc(input_size, acl.rt.ACL_MEM_MALLOC_HUGE_FIRST)
        if ret != 0:
            raise RuntimeError(f"分配输入内存失败: {ret}")

        # 拷贝输入数据
        ret = acl.rt.memcpy(
            input_ptr, input_size,
            input_data.ctypes.data, input_size,
            acl.rt.ACL_MEMCPY_HOST_TO_DEVICE
        )
        if ret != 0:
            raise RuntimeError(f"拷贝输入数据失败: {ret}")

        # 创建输入 Dataset
        input_dataset = acl.mdlCreateDataset()
        input_buffer = acl.create_data_buffer(input_ptr, input_size)
        ret = acl.mdlAddDatasetBuffer(input_dataset, input_buffer)
        if ret != 0:
            raise RuntimeError(f"添加输入缓冲区失败: {ret}")

        # 创建输出 Dataset
        output_dataset = acl.mdlCreateDataset()
        output_count = acl.mdlGetNumOutputs(self._model_desc)

        output_buffers = []
        for i in range(output_count):
            output_size = acl.mdlGetOutputSizeByIndex(self._model_desc, i)
            output_ptr, ret = acl.rt.malloc(output_size, acl.rt.ACL_MEM_MALLOC_HUGE_FIRST)
            if ret != 0:
                raise RuntimeError(f"分配输出内存失败: {ret}")

            output_buffer = acl.create_data_buffer(output_ptr, output_size)
            ret = acl.mdlAddDatasetBuffer(output_dataset, output_buffer)
            if ret != 0:
                raise RuntimeError(f"添加输出缓冲区失败: {ret}")

            output_buffers.append((output_ptr, output_size))

        # 执行推理
        ret = acl.mdlExecute(self._model_id, input_dataset, output_dataset)
        if ret != 0:
            raise RuntimeError(f"执行推理失败: {ret}")

        # 读取输出数据
        outputs = []
        for i, (output_ptr, output_size) in enumerate(output_buffers):
            # 获取输出 shape
            dims = acl.mdlGetOutputDims(self._model_desc, i)
            shape = dims['dims']

            # 分配主机内存
            output_data = np.zeros(output_size // 4, dtype=np.float32)

            # 拷贝输出数据
            ret = acl.rt.memcpy(
                output_data.ctypes.data, output_size,
                output_ptr, output_size,
                acl.rt.ACL_MEMCPY_DEVICE_TO_HOST
            )
            if ret != 0:
                raise RuntimeError(f"拷贝输出数据失败: {ret}")

            # 重塑为正确的 shape
            output_data = output_data.reshape(shape)
            outputs.append(output_data)

        # 释放资源
        acl.rt.free(input_ptr)
        for output_ptr, _ in output_buffers:
            acl.rt.free(output_ptr)

        acl.mdlDestroyDataset(input_dataset)
        acl.mdlDestroyDataset(output_dataset)

        return outputs

    def detect(self, frame: np.ndarray) -> List[DetectionResult]:
        """检测图像中的手部姿态.

        Args:
            frame: 输入图像 (BGR)

        Returns:
            List[DetectionResult]: 检测结果列表
        """
        if frame is None or frame.size == 0:
            logger.warning("输入图像为空")
            return []

        original_shape = frame.shape[:2]

        # PyTorch 后端使用 YOLO API 直接推理
        if self.backend == Backend.PYTORCH:
            return self._detect_pytorch(frame)

        # 预处理
        preprocessed, letterbox_info = self.preprocess(frame)

        # 推理
        try:
            if self.backend == Backend.ONNX:
                outputs = self._run_onnx(preprocessed)
            elif self.backend == Backend.CANN:
                outputs = self._run_cann(preprocessed)
            else:
                raise ValueError(f"不支持的后端: {self.backend}")
        except Exception as e:
            logger.error(f"推理失败: {e}")
            return []

        # 后处理
        results = self.postprocess(outputs, letterbox_info, original_shape)

        return results

    def _detect_pytorch(self, frame: np.ndarray) -> List[DetectionResult]:
        """使用 PyTorch 后端检测.

        Args:
            frame: 输入图像 (BGR)

        Returns:
            List[DetectionResult]: 检测结果列表
        """
        # 使用 YOLO API
        results = self._model.predict(
            frame,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            imgsz=self.imgsz,
            verbose=False,
        )

        detections = []
        for result in results:
            if result.keypoints is None:
                continue

            # 获取检测结果
            boxes = result.boxes.xyxy.cpu().numpy()
            confs = result.boxes.conf.cpu().numpy()
            kpts = result.keypoints.data.cpu().numpy()  # [N, 21, 3]

            for i in range(len(boxes)):
                detections.append(DetectionResult(
                    bbox=boxes[i],
                    keypoints_21=kpts[i],
                    confidence=float(confs[i]),
                ))

        return detections

    def release(self) -> None:
        """释放资源."""
        if self.backend == Backend.CANN:
            try:
                import acl
                acl.mdlDestroyDesc(self._model_desc)
                acl.mdlUnload(self._model_id)
                acl.aclContextDestroy(self._acl_context)
                acl.aclConfigDestroy(self._acl_config)
                acl.finalize()
                logger.info("CANN ACL 资源已释放")
            except Exception as e:
                logger.warning(f"释放 CANN 资源时出错: {e}")

        self._model = None
        self._session = None
        logger.info("资源已释放")

    def __del__(self) -> None:
        """析构函数."""
        self.release()


def parse_args() -> argparse.Namespace:
    """解析命令行参数.

    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(
        description="手部姿态检测器"
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="模型文件路径（支持 .pt, .onnx, .om）",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="auto",
        choices=["auto", "pytorch", "onnx", "cann"],
        help="推理后端 (默认: auto)",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.5,
        help="置信度阈值 (默认: 0.5)",
    )
    parser.add_argument(
        "--iou",
        type=float,
        default=0.45,
        help="NMS IoU 阈值 (默认: 0.45)",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="输入图片尺寸 (默认: 640)",
    )
    parser.add_argument(
        "--image",
        type=str,
        default=None,
        help="测试图片路径",
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=None,
        help="摄像头 ID",
    )
    return parser.parse_args()


def main() -> None:
    """主函数（用于测试）."""
    args = parse_args()

    # 创建检测器
    detector = PoseDetector(
        model_path=args.model,
        backend=args.backend,
        conf_threshold=args.conf,
        iou_threshold=args.iou,
        imgsz=args.imgsz,
    )

    # 测试图片
    if args.image:
        image = cv2.imread(args.image)
        if image is None:
            logger.error(f"无法读取图片: {args.image}")
            sys.exit(1)

        results = detector.detect(image)
        logger.info(f"检测到 {len(results)} 个手部:")
        for i, result in enumerate(results):
            logger.info(f"  手部 {i + 1}:")
            logger.info(f"    BBox: {result.bbox}")
            logger.info(f"    置信度: {result.confidence:.3f}")
            logger.info(f"    关键点: {result.keypoints_21.shape}")

    # 测试摄像头
    elif args.camera is not None:
        cap = cv2.VideoCapture(args.camera)
        if not cap.isOpened():
            logger.error(f"无法打开摄像头: {args.camera}")
            sys.exit(1)

        logger.info("按 'q' 退出")
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            results = detector.detect(frame)

            # 绘制结果
            for result in results:
                x1, y1, x2, y2 = result.bbox.astype(int)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                for kpt in result.keypoints_21:
                    x, y = int(kpt[0]), int(kpt[1])
                    cv2.circle(frame, (x, y), 3, (0, 0, 255), -1)

            cv2.imshow("Hand Pose Detection", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

    else:
        logger.info("请指定 --image 或 --camera 参数进行测试")

    detector.release()


if __name__ == "__main__":
    main()
