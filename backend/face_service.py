import os
import pickle
import logging
import threading
from pathlib import Path
import numpy as np
import cv2
from insightface.app import FaceAnalysis
from backend.config import EMBEDDINGS_CACHE_FILE

logger = logging.getLogger(__name__)

class FaceService:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(FaceService, cls).__new__(cls, *args, **kwargs)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.app = None
        self.init_lock = threading.Lock()
        self._initialized = True

    def initialize(self):
        """Loads InsightFace model into memory."""
        with self.init_lock:
            if self.app is None:
                logger.info("Initializing InsightFace FaceAnalysis (buffalo_l)...")
                # ctx_id=-1 forces CPU execution. 
                # For ONNX Runtime on CPU, CPUExecutionProvider is used.
                self.app = FaceAnalysis(name='buffalo_l')
                self.app.prepare(ctx_id=-1, det_size=(640, 640))
                logger.info("InsightFace FaceAnalysis initialized successfully.")

    def extract_embedding(self, img_bytes: bytes, filename: str) -> np.ndarray:
        """
        Decodes image, detects face, validates that exactly 1 face exists,
        and returns the 512-dim L2-normalized embedding.
        """
        if self.app is None:
            self.initialize()

        # Decode image using opencv
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Image {filename} is invalid or corrupted.")

        # Detect faces
        faces = self.app.get(img)
        if len(faces) == 0:
            raise ValueError(f"No face detected in image: {filename}")
        if len(faces) > 1:
            raise ValueError(f"Multiple faces ({len(faces)}) detected in image: {filename}")

        # Get embedding and L2 normalize
        embedding = faces[0].embedding
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        return embedding

    def detect_all_faces(self, img: np.ndarray) -> list:
        """
        Detects all faces in an OpenCV image frame.
        Returns a list of dicts, each containing:
          - "bbox": bounding box list [x1, y1, x2, y2]
          - "embedding": 512-dim L2-normalized numpy array
        """
        if self.app is None:
            self.initialize()

        faces = self.app.get(img)
        results = []
        for face in faces:
            embedding = face.embedding
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            results.append({
                "bbox": face.bbox.tolist(),
                "embedding": embedding
            })
        return results

    def compute_average_embedding(self, embeddings: list) -> np.ndarray:
        """Computes L2-normalized average embedding from a list of embeddings."""
        if not embeddings:
            raise ValueError("Embeddings list cannot be empty.")
        avg_emb = np.mean(embeddings, axis=0)
        norm = np.linalg.norm(avg_emb)
        if norm > 0:
            avg_emb = avg_emb / norm
        return avg_emb

    def load_all_embeddings(self) -> dict:
        """Loads all embeddings from the pickle file thread-safely."""
        if not EMBEDDINGS_CACHE_FILE.exists():
            return {}
        with self._lock:
            try:
                with open(EMBEDDINGS_CACHE_FILE, "rb") as f:
                    return pickle.load(f)
            except Exception as e:
                logger.error(f"Error reading embeddings pickle: {e}")
                return {}

    def save_all_embeddings(self, embeddings_dict: dict):
        """Saves embeddings dictionary to the pickle file thread-safely."""
        with self._lock:
            try:
                EMBEDDINGS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(EMBEDDINGS_CACHE_FILE, "wb") as f:
                    pickle.dump(embeddings_dict, f)
                logger.info(f"Saved {len(embeddings_dict)} embeddings to cache.")
            except Exception as e:
                logger.error(f"Error writing embeddings pickle: {e}")
                raise e

    def update_student_embedding(self, student_id: str, embedding: np.ndarray):
        """Updates or inserts a student's embedding."""
        embeddings = self.load_all_embeddings()
        embeddings[student_id] = embedding
        self.save_all_embeddings(embeddings)

    def delete_student_embedding(self, student_id: str):
        """Removes a student's embedding if it exists."""
        embeddings = self.load_all_embeddings()
        if student_id in embeddings:
            del embeddings[student_id]
            self.save_all_embeddings(embeddings)
