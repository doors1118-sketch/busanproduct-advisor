# Contract Source Activation Review Notes

## 1. Excluded / Pending Sources
- **계약내용과 상이한 물품의 반송 또는 수출 신고수리에 관한 예규**: Excluded due to review_status: wrong_match
- **부산광역시 지역상품 우선구매 관련 조례**: Excluded due to review_status: needs_manual_source
- **부산광역시 지역업체ㆍ지역상품 우대 관련 자치법규**: Excluded due to review_status: needs_manual_source

## 2. Validation Checks
- [X] No source upgraded without activation_mode
- [X] PPS routes correctly tagged with procurement_route_required
- [X] Local autonomous contracts isolated from PPS rules
- [X] Public housing explicitly uses project_subtype=public_housing
- [X] Temporary exemptions use time_bounded
- [X] wrong_match and needs_manual_source remain inactive
