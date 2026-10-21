/**
 * @file add_custom.cpp  (template filename retained for the sample build system)
 *
 * Host stub for the EphemeralCoreApply ACLNN custom op (MWG-EW arm 4).
 * Semantics:  scaled_rank_activation = rank_activation
 *               * (1 + amplitude * tanh(controller_hidden @ head_weight + head_bias))
 * with rank_activation [T, R] fp16, controller_hidden [T, H] fp32,
 * head_weight [H, R] fp32, head_bias [R] fp32, amplitude float attr.
 * The generated diagonal core exists only in the kernel's UB scratch.
 */
#include "add_custom_tiling.h"
#include "register/op_def_registry.h"

namespace optiling {
const uint32_t BLOCK_DIM = 1;  // v1: one core processes every M tile
static ge::graphStatus TilingFunc(gert::TilingContext *context)
{
    TilingData tiling;
    uint32_t tokenCount = context->GetInputShape(0)->GetOriginShape().GetDim(0);
    uint32_t rankDim = context->GetInputShape(0)->GetOriginShape().GetDim(1);
    uint32_t hiddenDim = context->GetInputShape(1)->GetOriginShape().GetDim(1);
    const gert::RuntimeAttrs *attrs = context->GetAttrs();
    const float *amplitude = attrs->GetAttrPointer<float>(0);
    uint32_t tileNum = (tokenCount + 7) / 8;  // TILE_M = 8 in the kernel
    context->SetBlockDim(BLOCK_DIM);
    tiling.set_tokenCount(tokenCount);
    tiling.set_hiddenDim(hiddenDim);
    tiling.set_rankDim(rankDim);
    tiling.set_amplitude(*amplitude);
    tiling.set_tileNum(tileNum);
    tiling.SaveToBuffer(context->GetRawTilingData()->GetData(),
                        context->GetRawTilingData()->GetCapacity());
    context->GetRawTilingData()->SetDataSize(tiling.GetDataSize());
    size_t *currentWorkspace = context->GetWorkspaceSizes(1);
    currentWorkspace[0] = 0;  // zero workspace: contract workspace_bytes = 0
    return ge::GRAPH_SUCCESS;
}
}  // namespace optiling

namespace ge {
static graphStatus InferShape(gert::InferShapeContext *context)
{
    const gert::Shape *inShape = context->GetInputShape(0);
    gert::Shape *outShape = context->GetOutputShape(0);
    *outShape = *inShape;
    return GRAPH_SUCCESS;
}
static graphStatus InferDataType(gert::InferDataTypeContext *context)
{
    const ge::DataType inType = context->GetInputDataType(0);
    context->SetOutputDataType(0, inType);
    return GRAPH_SUCCESS;
}
}  // namespace ge

namespace ops {
class EphemeralCoreApply : public OpDef {
public:
    explicit EphemeralCoreApply(const char *name) : OpDef(name)
    {
        this->Input("rank_activation")
            .ParamType(REQUIRED)
            .DataType({ge::DT_FLOAT16})
            .Format({ge::FORMAT_ND});
        this->Input("controller_hidden")
            .ParamType(REQUIRED)
            .DataType({ge::DT_FLOAT})
            .Format({ge::FORMAT_ND});
        this->Input("head_weight")
            .ParamType(REQUIRED)
            .DataType({ge::DT_FLOAT})
            .Format({ge::FORMAT_ND});
        this->Input("head_bias")
            .ParamType(REQUIRED)
            .DataType({ge::DT_FLOAT})
            .Format({ge::FORMAT_ND});
        this->Attr("amplitude").AttrType(OPTIONAL).Float(0.05);
        this->Output("scaled_rank_activation")
            .ParamType(REQUIRED)
            .DataType({ge::DT_FLOAT16})
            .Format({ge::FORMAT_ND});
        this->SetInferShape(ge::InferShape).SetInferDataType(ge::InferDataType);
        // ascend910b is the CANN 8.5 soc name for the 910B family
        // (Ascend910B2 devices); other spellings are rejected by opbuild.
        this->AICore().SetTiling(optiling::TilingFunc).AddConfig("ascend910b");
    }
};
OP_ADD(EphemeralCoreApply);
}  // namespace ops
