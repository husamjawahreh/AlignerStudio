# official_real_case_stage2_verified_v1

Official ToothInstanceNet real-case Stage-2 instance segmentation artifact.

Verified:
- Real lower.stl and upper.stl
- Official ToothInstanceNet instance checkpoint
- Official alignment checkpoint
- PointOps rebuilt for Tesla T4 with FPS thread cap 256
- DataModule num_classes = 7
- Official `instances` inference
- 2/2 real scans processed
- Segmentation artifacts written successfully
- Semantic audit passed
- Repository source was not persistently modified

The 7-class configuration does not constitute exact 28-tooth FDI
anatomical identification or clinical accuracy validation.
