# AI3 MWG-EW Reliability and Scaling Summary

| Group | Runs | Method | Train ms mean | Train ms std | Train speedup mean | AllReduce ms mean | Traffic reduction | Train tok/s mean |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| world1_devices0_presetai3_sweep | 3 | dense | 4.9742 | 0.0239 | None | 0.0 | None | 205866.7933 |
| world1_devices0_presetai3_sweep | 3 | mwg_r64 | 3.3785 | 0.1928 | 1.475 | 0.0 | 49.778 | 303731.71 |
| world1_devices0_presetai3_sweep | 3 | mwg_r128 | 3.2545 | 0.1694 | 1.5307 | 0.0 | 24.889 | 315193.7867 |
| world1_devices0_presetai3_sweep | 3 | mwg_r256 | 3.2879 | 0.1327 | 1.5143 | 0.0 | 12.444 | 311780.17 |
| world2_devices0,1_presetai3_sweep | 3 | dense | 5.8624 | 0.7332 | None | 19.6627 | None | 352778.4033 |
| world2_devices0,1_presetai3_sweep | 3 | mwg_r64 | 3.9907 | 0.1104 | 1.4717 | 1.2599 | 49.778 | 513446.81 |
| world2_devices0,1_presetai3_sweep | 3 | mwg_r128 | 4.7966 | 1.5295 | 1.2677 | 1.6772 | 24.889 | 452995.7567 |
| world2_devices0,1_presetai3_sweep | 3 | mwg_r256 | 3.8896 | 0.0662 | 1.5067 | 2.5398 | 12.444 | 526639.4833 |
| world4_devices0,1,2,3_presetai3_sweep | 3 | dense | 6.1351 | 1.1496 | None | 11.4896 | None | 682036.33 |
| world4_devices0,1,2,3_presetai3_sweep | 3 | mwg_r64 | 4.1078 | 0.1168 | 1.4967 | 1.1655 | 49.778 | 997656.15 |
| world4_devices0,1,2,3_presetai3_sweep | 3 | mwg_r128 | 4.4547 | 0.6583 | 1.412 | 1.4632 | 24.889 | 932103.8167 |
| world4_devices0,1,2,3_presetai3_sweep | 3 | mwg_r256 | 4.1109 | 0.0797 | 1.4963 | 1.8239 | 12.444 | 996635.7933 |
| world8_devices0,1,2,3,4,5,6,7_presetai3_sweep | 3 | dense | 6.4874 | 0.8606 | None | 6.9101 | None | 1278570.42 |
| world8_devices0,1,2,3,4,5,6,7_presetai3_sweep | 3 | mwg_r64 | 4.8044 | 1.1034 | 1.3727 | 1.1549 | 49.778 | 1760478.27 |
| world8_devices0,1,2,3,4,5,6,7_presetai3_sweep | 3 | mwg_r128 | 4.2047 | 0.0299 | 1.542 | 1.2786 | 24.889 | 1948377.0767 |
| world8_devices0,1,2,3,4,5,6,7_presetai3_sweep | 3 | mwg_r256 | 4.1222 | 0.2432 | 1.5717 | 1.4182 | 12.444 | 1991912.7733 |
