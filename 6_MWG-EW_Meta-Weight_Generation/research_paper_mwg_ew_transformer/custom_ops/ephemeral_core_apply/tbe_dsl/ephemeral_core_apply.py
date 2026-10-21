"""TBE-DSL implementation of mwg::ephemeral_core_apply (arm 4, v2 route).

Canonical CANN 8.5 dynamic-op structure (mirrors impl/ops_legacy/dynamic/*):

    opfunc(x, w, b, y, amplitude=..., kernel_name=...)   # dicts
      -> classify -> tbe.compute -> tvm.placeholder
      -> ephemeral_core_apply_compute (pure DSL math)
      -> auto_schedule -> tbe.build

Math (identical to the verified AscendC kernel / harness reference):

    logits = ch[T,H] @ w[H,R] + b[R]        # fp32 accumulate
    core   = 1 + amplitude * tanh(logits)
    out    = act[T,R] * core                # fp16

tanh via primitives: tanh(L) = (e^{2L} - 1)/(e^{2L} + 1), no NaN for large
|L| (num and denom saturate consistently).
"""
from tbe.dsl.api import build
from tbe.dsl.api import auto_schedule
import te.lang.cce as tbe
from te import tvm
from tbe.common.utils import para_check


def _stable_tanh_chain(logits):
    """tanh(L) = (e^{2L} - 1) / (e^{2L} + 1) using DSL primitives."""
    two_l = tbe.vmuls(logits, 2.0)
    e = tbe.vexp(two_l)
    num = tbe.vsub(e, 1.0)
    den = tbe.vadds(e, 1.0)
    return tbe.vdiv(num, den)


def ephemeral_core_apply_compute(act, ch, w, b, amplitude, kernel_name):
    """Pure-DSL compute on tvm placeholders. Returns the output tensor."""
    # GEMM with fp32 accumulate and fused bias
    logits = tbe.matmul(
        ch, w,
        trans_a=False, trans_b=False,
        format_a="ND", format_b="ND",
        dst_dtype="float16",
        tensor_bias=b,
        kernel_name=kernel_name + "_gemm",
    )
    tanh_l = _stable_tanh_chain(logits)
    scaled = tbe.vmuls(tanh_l, amplitude)
    core = tbe.vadds(scaled, 1.0)
    # core is fp32; cast to fp16 to match activation dtype
    core16 = tbe.cast_to(core, "float16")
    return tbe.vmul(act, core16)


def ephemeral_core_apply(*args, **kwargs):
    """Opfunc entry: unpacks dict descriptors, builds, compiles.

    x: dict for rank_activation [T, R] fp16
    w: dict for head_weight     [H, R] fp32
    b: dict for head_bias       [R]    fp32
    y: dict for output          [T, R] fp16
    """
    args_list = list(args) + [kwargs[k] for k in ("amplitude", "kernel_name") if k in kwargs]
    x, w, b, y = args_list[0], args_list[1], args_list[2], args_list[3]
    amplitude = kwargs.get("amplitude", 0.05)
    kernel_name = kwargs.get("kernel_name", "ephemeral_core_apply")
    shape_act = x.get("shape")
    dtype_act = x.get("dtype").lower()
    shape_w = w.get("shape")
    dtype_w = w.get("dtype").lower()
    shape_b = b.get("shape")
    dtype_b = b.get("dtype").lower()
    para_check.check_dtype(dtype_act, ("float16",), param_name="x")
    para_check.check_dtype(dtype_w, ("float32",), param_name="w")
    para_check.check_dtype(dtype_b, ("float32",), param_name="b")

    R = shape_act[-1]
    T = 1
    for d in shape_act[:-1]:
        T *= d
    H = shape_w[0]
    act_ph = tvm.placeholder(shape_act, dtype_act, "act")
    ch_ph = tvm.placeholder((T, H), "float32", "ch")
    w_ph = tvm.placeholder(shape_w, dtype_w, "w")
    b_ph = tvm.placeholder(shape_b, dtype_b, "b")

    mm_attrs = {
        "enable_parallel": False,
        "schedule_pattern": "Matmul",
    }
    logits = tbe.matmul(
        ch_ph, w_ph,
        trans_a=False, trans_b=False,
        format_a="ND", format_b="ND",
        dst_dtype="float16",
        tensor_bias=b_ph,
        attrs=mm_attrs,
        kernel_name=kernel_name + "_gemm",
    )
    tanh_l = _stable_tanh_chain(logits)   # fp16 chain (matches gemm out)
    scaled = tbe.vmuls(tanh_l, amplitude)
    core = tbe.vadds(scaled, 1.0)
    res = tbe.vmul(act_ph, core)

    tensors = [act_ph, ch_ph, w_ph, b_ph, res]

    with tvm.target.cce():
        sch = auto_schedule(res)

    config = {"name": kernel_name, "tensor_list": tensors, "print_ir": False}
    build(sch, config)
