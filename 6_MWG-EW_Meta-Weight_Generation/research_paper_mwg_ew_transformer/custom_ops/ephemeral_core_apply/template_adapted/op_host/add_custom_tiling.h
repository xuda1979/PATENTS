/**
 * @file add_custom_tiling.h  (template filename retained for the sample build)
 *
 * Tiling data for EphemeralCoreApply.  All scalar launch parameters travel
 * through tiling; no workspace is required.
 */
#ifndef ADD_CUSTOM_TILING_H
#define ADD_CUSTOM_TILING_H
#include "register/tilingdata_base.h"
namespace optiling {
BEGIN_TILING_DATA_DEF(TilingData)
TILING_DATA_FIELD_DEF(uint32_t, tokenCount);
TILING_DATA_FIELD_DEF(uint32_t, hiddenDim);
TILING_DATA_FIELD_DEF(uint32_t, rankDim);
TILING_DATA_FIELD_DEF(float, amplitude);
TILING_DATA_FIELD_DEF(uint32_t, tileNum);
END_TILING_DATA_DEF;
REGISTER_TILING_DATA_CLASS(EphemeralCoreApply, TilingData)
}  // namespace optiling
#endif  // ADD_CUSTOM_TILING_H
