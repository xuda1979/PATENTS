from __future__ import annotations

import copy
import hashlib
import math
from dataclasses import dataclass

import numpy as np
from sympy import Matrix


@dataclass(frozen=True)
class TitanParams:
    name: str
    N: int
    p: int
    rounds: int
    t0_seed: int = 42


class TitanSignature:
    """Integer-only TITAN proof-of-concept implementation.

    This implementation deliberately avoids floating-point arithmetic and uses
    only finite-field matrix operations plus tensor contractions.
    """

    def __init__(self, params: TitanParams, rng_seed: int = 12345) -> None:
        self.params = params
        self.N = params.N
        self.p = params.p
        self.rounds = params.rounds
        self.rng = np.random.default_rng(rng_seed)
        t0_rng = np.random.default_rng(params.t0_seed)
        self.T0 = t0_rng.integers(0, self.p, size=(self.N, self.N, self.N), dtype=np.int64)
        self.coeff_bytes = max(1, math.ceil((self.p - 1).bit_length() / 8))

    def _pack_dtype(self) -> np.dtype:
        if self.coeff_bytes == 1:
            return np.dtype(np.uint8)
        if self.coeff_bytes == 2:
            return np.dtype("<u2")
        if self.coeff_bytes <= 4:
            return np.dtype("<u4")
        return np.dtype("<u8")

    def _mod_inv(self, matrix: np.ndarray) -> np.ndarray:
        inv = Matrix(matrix.tolist()).inv_mod(self.p)
        return np.array(inv.tolist(), dtype=np.int64) % self.p

    def _rand_nonzero(self) -> int:
        return int(self.rng.integers(1, self.p))

    def _rand_invertible_matrix(self) -> np.ndarray:
        """Generate an invertible matrix without rejection sampling.

        We start from identity and apply random invertible row operations.
        This keeps generation deterministic and avoids repeated trial loops.
        """
        matrix = np.eye(self.N, dtype=np.int64)
        for row in range(self.N):
            matrix[row] = (matrix[row] * self._rand_nonzero()) % self.p
        perm = self.rng.permutation(self.N)
        matrix = matrix[perm]
        for _ in range(3 * self.N):
            src, dst = self.rng.choice(self.N, size=2, replace=False)
            coeff = self._rand_nonzero()
            matrix[dst] = (matrix[dst] + coeff * matrix[src]) % self.p
        return matrix

    def tensor_action(
        self,
        tensor: np.ndarray,
        A: np.ndarray,
        B: np.ndarray,
        C: np.ndarray,
    ) -> np.ndarray:
        result = np.einsum(
            "ix,jy,kz,xyz->ijk",
            A,
            B,
            C,
            tensor,
            optimize=True,
            dtype=np.int64,
        )
        return result % self.p

    def keygen(self) -> tuple[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray], np.ndarray]:
        U = self._rand_invertible_matrix()
        V = self._rand_invertible_matrix()
        W = self._rand_invertible_matrix()
        U_inv = self._mod_inv(U)
        V_inv = self._mod_inv(V)
        W_inv = self._mod_inv(W)
        pk = self.tensor_action(self.T0, U, V, W)
        sk = (U, V, W, U_inv, V_inv, W_inv)
        return sk, pk

    def sign(
        self,
        message: bytes,
        secret_key: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    ) -> tuple[bytes, list[tuple[np.ndarray, np.ndarray, np.ndarray]]]:
        _, _, _, U_inv, V_inv, W_inv = secret_key
        masks: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
        commitments: list[np.ndarray] = []
        for _ in range(self.rounds):
            RA = self._rand_invertible_matrix()
            RB = self._rand_invertible_matrix()
            RC = self._rand_invertible_matrix()
            masks.append((RA, RB, RC))
            commitments.append(self.tensor_action(self.T0, RA, RB, RC))

        root_hash = hashlib.sha256(self._hash_material(message, commitments)).digest()
        challenges = self.hash_to_challenges(root_hash)

        responses: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
        for challenge, (RA, RB, RC) in zip(challenges, masks):
            if challenge == 0:
                responses.append((RA, RB, RC))
            else:
                responses.append(
                    (
                        (RA @ U_inv) % self.p,
                        (RB @ V_inv) % self.p,
                        (RC @ W_inv) % self.p,
                    )
                )
        return root_hash, responses

    def verify(
        self,
        message: bytes,
        signature: tuple[bytes, list[tuple[np.ndarray, np.ndarray, np.ndarray]]],
        public_key: np.ndarray,
    ) -> bool:
        root_hash, responses = signature
        challenges = self.hash_to_challenges(root_hash)
        commitments: list[np.ndarray] = []
        for challenge, (A, B, C) in zip(challenges, responses):
            if challenge == 0:
                commitments.append(self.tensor_action(self.T0, A, B, C))
            else:
                commitments.append(self.tensor_action(public_key, A, B, C))
        recomputed = hashlib.sha256(self._hash_material(message, commitments)).digest()
        return recomputed == root_hash

    def hash_to_challenges(self, root_hash: bytes) -> list[int]:
        out: list[int] = []
        for i in range(self.rounds):
            out.append((root_hash[i // 8] >> (i % 8)) & 1)
        return out

    def _hash_material(self, message: bytes, commitments: list[np.ndarray]) -> bytes:
        payload = bytearray(message)
        for commitment in commitments:
            payload.extend(self.pack_tensor(commitment))
        return bytes(payload)

    def pack_tensor(self, tensor: np.ndarray) -> bytes:
        return np.asarray(tensor % self.p, dtype=self._pack_dtype()).tobytes(order="C")

    def pack_matrix(self, matrix: np.ndarray) -> bytes:
        return np.asarray(matrix % self.p, dtype=self._pack_dtype()).tobytes(order="C")

    def signature_size_bytes(self, signature: tuple[bytes, list[tuple[np.ndarray, np.ndarray, np.ndarray]]]) -> int:
        root_hash, responses = signature
        total = len(root_hash)
        for mats in responses:
            for matrix in mats:
                total += len(self.pack_matrix(matrix))
        return total

    def public_key_size_bytes(self, public_key: np.ndarray) -> int:
        return len(self.pack_tensor(public_key))

    def secret_key_size_bytes(
        self,
        secret_key: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    ) -> int:
        total = 0
        for matrix in secret_key:
            total += len(self.pack_matrix(matrix))
        return total

    @staticmethod
    def clone_signature(
        signature: tuple[bytes, list[tuple[np.ndarray, np.ndarray, np.ndarray]]],
    ) -> tuple[bytes, list[tuple[np.ndarray, np.ndarray, np.ndarray]]]:
        root_hash, responses = signature
        copied: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
        for A, B, C in responses:
            copied.append((A.copy(), B.copy(), C.copy()))
        return bytes(root_hash), copied

    def tamper_signature(
        self,
        signature: tuple[bytes, list[tuple[np.ndarray, np.ndarray, np.ndarray]]],
    ) -> tuple[bytes, list[tuple[np.ndarray, np.ndarray, np.ndarray]]]:
        root_hash, responses = self.clone_signature(signature)
        tampered_hash = bytearray(root_hash)
        tampered_hash[0] ^= 0x01
        if responses:
            A, B, C = responses[0]
            A[0, 0] = (int(A[0, 0]) + 1) % self.p
        return bytes(tampered_hash), responses
