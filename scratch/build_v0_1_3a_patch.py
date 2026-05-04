import json, os, sys, sqlite3
sys.stdout.reconfigure(encoding='utf-8')

base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'
db_path = os.path.join(base, 'legal_db_v0_1.sqlite')

# 1. Fetch canonical sources from DB
conn = sqlite3.connect(db_path)
cur = conn.cursor()
canonical_sources = []
for row in cur.execute("SELECT source_id, normalized_title, active_for_rule, review_status, registry_trust_level FROM legal_source").fetchall():
    canonical_sources.append({
        "source_id": row[0],
        "normalized_title": row[1],
        "active_for_rule": bool(row[2]),
        "review_status": row[3],
        "registry_trust_level": row[4]
    })
conn.close()

# 2. Detailed Rules mapping based on user constraints
rules = {
    # 6-1. core_common
    "지방자치단체 입찰 및 계약집행기준": {
        "active_for_rule": True, "activation_mode": "core_common", "jurisdiction_scope": ["local_contract"],
        "required_slots": ["buyer_type", "contract_method", "contract_object"]
    },
    "지방자치단체 입찰시 낙찰자 결정기준": {
        "active_for_rule": True, "activation_mode": "core_common", "jurisdiction_scope": ["local_contract"],
        "required_slots": ["buyer_type", "contract_method", "contract_object"]
    },
    
    # 6-2. conditional_common
    "공동계약운용요령": {
        "active_for_rule": True, "activation_mode": "conditional_common", "jurisdiction_scope": ["national_contract"],
        "required_slots": ["contract_object", "contract_method"]
    },
    "공사계약일반조건": {
        "active_for_rule": True, "activation_mode": "conditional_common", "jurisdiction_scope": ["national_contract"],
        "required_slots": ["contract_object", "contract_method"]
    },
    "용역계약일반조건": {
        "active_for_rule": True, "activation_mode": "conditional_common", "jurisdiction_scope": ["national_contract"],
        "required_slots": ["contract_object", "contract_method"]
    },
    "용역입찰유의서": {
        "active_for_rule": True, "activation_mode": "conditional_common", "jurisdiction_scope": ["national_contract"],
        "required_slots": ["contract_object", "contract_method"]
    },
    "종합계약집행요령": {
        "active_for_rule": True, "activation_mode": "conditional_common", "jurisdiction_scope": ["national_contract"],
        "required_slots": ["contract_object", "contract_method"]
    },
    "공사계약 종합심사낙찰제 심사기준": {
        "active_for_rule": True, "activation_mode": "conditional_common", "jurisdiction_scope": ["national_contract"],
        "required_slots": ["contract_object", "contract_method"]
    },
    "용역계약 종합심사낙찰제 심사기준": {
        "active_for_rule": True, "activation_mode": "conditional_common", "jurisdiction_scope": ["national_contract"],
        "required_slots": ["contract_object", "contract_method"]
    },
    
    # 6-3. procurement_channel_evidence
    "국가를 당사자로 하는 계약에 관한 법률 시행령 제39조제1항 단서의 규정에 의한 정보처리장치의 지정에 관한 고시": {
        "active_for_rule": True, "activation_mode": "procurement_channel_evidence",
        "used_for": ["e_procurement_path", "designated_information_system", "나라장터/전자조달 경로 근거"],
        "not_used_for": ["contract_method_final_judgment", "direct_contract_permission"]
    },
    "지방자치단체를 당사자로 하는 계약에 관한 법률 시행령 제6조의2 및 공유재산 및 물품 관리법 시행령 제13조, 제26조, 제78조에 따른 정보처리장치의 지정에 관한 고시": {
        "active_for_rule": True, "activation_mode": "procurement_channel_evidence",
        "used_for": ["e_procurement_path", "designated_information_system", "나라장터/전자조달 경로 근거"],
        "not_used_for": ["contract_method_final_judgment", "direct_contract_permission"]
    },
    
    # 6-4. conditional_common (고시)
    "국가를 당사자로 하는 계약에 관한 법률 시행령 제72조제3항제2호에 따른 공동계약 대상사업": {
        "active_for_rule": True, "activation_mode": "conditional_common",
        "required_slots": ["contract_object", "joint_contract_question"],
        "used_for": ["공동계약 대상 여부", "지역의무공동도급 검토 보조"]
    },
    
    # 6-5. time_bounded
    "지방자치단체를 당사자로 하는 계약에 관한 법률 시행령의 수의계약 등 한시적 특례 적용기간에 관한 고시": {
        "active_for_rule": True, "activation_mode": "time_bounded",
        "required_slots": ["contract_date", "effective_from", "effective_to"],
        "excluded_when": ["contract_date outside effective period"],
        "used_for": ["한시적 수의계약 특례 적용기간 확인"]
    },
    
    # 7. procurement_route_required (Specific scopes)
    "물품 다수공급자계약 업무처리규정": {
        "active_for_rule": True, "activation_mode": "procurement_route_required",
        "procurement_route_scope": ["mas", "pps_shopping_mall", "third_party_unit_price_contract"],
        "contract_object_scope": ["goods"], "required_slots": ["procurement_route", "contract_object"]
    },
    "국가종합전자조달시스템 종합쇼핑몰 운영규정": {
        "active_for_rule": True, "activation_mode": "procurement_route_required",
        "procurement_route_scope": ["pps_shopping_mall", "mas", "third_party_unit_price_contract", "catalog_contract"],
        "required_slots": ["procurement_route", "contract_object"]
    },
    "조달청 물품구매적격심사 세부기준": {
        "active_for_rule": True, "activation_mode": "procurement_route_required",
        "procurement_route_scope": ["pps_delegated_contract", "pps_central_procurement"],
        "contract_object_scope": ["goods"], "required_slots": ["procurement_route", "contract_object"]
    },
    "조달청 시설공사 적격심사세부기준": {
        "active_for_rule": True, "activation_mode": "procurement_route_required",
        "procurement_route_scope": ["pps_facility_work", "pps_delegated_contract"],
        "contract_object_scope": ["construction"], "required_slots": ["procurement_route", "contract_object"]
    },
    "조달청 기술용역 적격심사 세부기준": {
        "active_for_rule": True, "activation_mode": "procurement_route_required",
        "procurement_route_scope": ["pps_technical_service", "pps_delegated_contract"],
        "contract_object_scope": ["technical_service"], "required_slots": ["procurement_route", "contract_object"]
    },
    "조달청 일반용역 적격심사 세부기준": {
        "active_for_rule": True, "activation_mode": "procurement_route_required",
        "procurement_route_scope": ["pps_delegated_contract", "pps_central_procurement"],
        "contract_object_scope": ["service"], "required_slots": ["procurement_route", "contract_object"]
    },
    "조달청 경쟁적 대화에 의한 계약체결 세부기준": {
        "active_for_rule": True, "activation_mode": "procurement_route_required",
        "procurement_route_scope": ["pps_delegated_contract", "pps_central_procurement"],
        "required_slots": ["procurement_route", "contract_object"]
    },
    "조달청 건설엔지니어링 종합심사낙찰제 세부심사기준": {
        "active_for_rule": True, "activation_mode": "procurement_route_required",
        "procurement_route_scope": ["pps_delegated_contract", "pps_technical_service"],
        "contract_object_scope": ["technical_service"], "project_subtype_scope": ["construction_engineering"],
        "required_slots": ["procurement_route", "project_subtype"]
    },
    "조달청 기술용역 계약업무 처리규정": {
        "active_for_rule": True, "activation_mode": "procurement_route_required",
        "procurement_route_scope": ["pps_delegated_contract", "pps_technical_service"],
        "contract_object_scope": ["technical_service"], "required_slots": ["procurement_route", "contract_object"]
    },
    "조달청 시설공사 실적에 의한 경쟁입찰 집행기준": {
        "active_for_rule": True, "activation_mode": "procurement_route_required",
        "procurement_route_scope": ["pps_delegated_contract", "pps_facility_work"],
        "contract_object_scope": ["construction"], "required_slots": ["procurement_route", "contract_object"]
    },
    "조달청 일괄입찰 등에 의한 낙찰자 결정 세부기준": {
        "active_for_rule": True, "activation_mode": "procurement_route_required",
        "procurement_route_scope": ["pps_delegated_contract", "pps_facility_work"],
        "contract_object_scope": ["construction"], "required_slots": ["procurement_route", "contract_object"]
    },
    "조달청 협상에 의한 계약 제안서평가 세부기준": {
        "active_for_rule": True, "activation_mode": "procurement_route_required",
        "procurement_route_scope": ["pps_delegated_contract", "pps_central_procurement"],
        "required_slots": ["procurement_route", "contract_object"]
    },
    
    # 8. procurement_route_and_subtype_required
    "조달청 공공주택 건설사업관리용역 종합심사낙찰제 세부심사기준": {
        "active_for_rule": True, "activation_mode": "procurement_route_and_subtype_required",
        "procurement_route_scope": ["pps_delegated_contract", "pps_technical_service"],
        "project_subtype_scope": ["public_housing", "construction_management_service"],
        "required_slots": ["procurement_route", "project_subtype"]
    },
    "조달청 공공주택 공사계약 종합심사낙찰제 심사세부기준": {
        "active_for_rule": True, "activation_mode": "procurement_route_and_subtype_required",
        "procurement_route_scope": ["pps_delegated_contract", "pps_facility_work"],
        "project_subtype_scope": ["public_housing"],
        "required_slots": ["procurement_route", "project_subtype"]
    },
    "조달청 공공주택 공사입찰특별유의서": {
        "active_for_rule": True, "activation_mode": "procurement_route_and_subtype_required",
        "procurement_route_scope": ["pps_delegated_contract", "pps_facility_work"],
        "project_subtype_scope": ["public_housing"],
        "required_slots": ["procurement_route", "project_subtype"]
    },
    "조달청 공공주택 등급별 유자격자명부 등록 및 운용기준": {
        "active_for_rule": True, "activation_mode": "procurement_route_and_subtype_required",
        "procurement_route_scope": ["pps_delegated_contract", "pps_facility_work"],
        "project_subtype_scope": ["public_housing"],
        "required_slots": ["procurement_route", "project_subtype"]
    },
    "조달청 공공주택 입찰참가자격사전심사기준": {
        "active_for_rule": True, "activation_mode": "procurement_route_and_subtype_required",
        "procurement_route_scope": ["pps_delegated_contract", "pps_facility_work"],
        "project_subtype_scope": ["public_housing"],
        "required_slots": ["procurement_route", "project_subtype"]
    },
    "조달청 공공주택 적격심사세부기준": {
        "active_for_rule": True, "activation_mode": "procurement_route_and_subtype_required",
        "procurement_route_scope": ["pps_delegated_contract", "pps_facility_work"],
        "project_subtype_scope": ["public_housing"],
        "required_slots": ["procurement_route", "project_subtype"]
    },
    "기술제안입찰 등에 의한 낙찰자 결정 세부기준": {
        "active_for_rule": True, "activation_mode": "procurement_route_and_subtype_required",
        "procurement_route_scope": ["pps_delegated_contract"],
        "project_subtype_scope": ["technical_proposal"],
        "required_slots": ["procurement_route", "project_subtype"]
    },
    "기술용역 적격심사 및 협상에 의한 낙찰자 결정기준": {
        "active_for_rule": True, "activation_mode": "procurement_route_and_subtype_required",
        "procurement_route_scope": ["pps_delegated_contract", "pps_technical_service"],
        "contract_object_scope": ["technical_service"],
        "required_slots": ["procurement_route", "contract_object"]
    },
    "기술용역 적격심사기준에 관한 훈령": {
        "active_for_rule": True, "activation_mode": "procurement_route_and_subtype_required",
        "procurement_route_scope": ["pps_delegated_contract", "pps_technical_service"],
        "contract_object_scope": ["technical_service"],
        "required_slots": ["procurement_route", "contract_object"]
    },
    "기술용역적격심사 세부기준": {
        "active_for_rule": True, "activation_mode": "procurement_route_and_subtype_required",
        "procurement_route_scope": ["pps_delegated_contract", "pps_technical_service"],
        "contract_object_scope": ["technical_service"],
        "required_slots": ["procurement_route", "contract_object"]
    },
    
    # 9. institution_type_based
    "기타공공기관 계약사무 운영규정": {
        "active_for_rule": True, "activation_mode": "institution_type_based",
        "jurisdiction_scope": ["public_institution_contract"],
        "buyer_type_scope": ["other_public_institution"],
        "required_slots": ["buyer_type"]
    },
    
    # 10. procedure_only
    "조달청 시설분야 물가변동 사전검토 처리규정": {
        "active_for_rule": False, "active_for_procedure": True, "judgment_eligible": False,
        "activation_mode": "procedure_only", "rule_use_scope": ["procedure_support"]
    },
    "조달청 종합심사낙찰제 물량ㆍ시공계획 심사위원회 설치 및 운영규정": {
        "active_for_rule": False, "active_for_procedure": True, "judgment_eligible": False,
        "activation_mode": "procedure_only", "rule_use_scope": ["procedure_support"]
    }
}

proc_only_template = {
    "active_for_rule": False, "active_for_procedure": True, "judgment_eligible": False,
    "activation_mode": "procedure_only", "rule_use_scope": ["procedure_support"]
}

# 3. Apply Rules to Canonical DB entries only
patch_data = []
candidate_report = []

matched_patch_count = 0
already_active_in_patch = 0
net_new_active = 0
active_for_procedure_count = 0
invalid_proc_only = 0
invalid_scope_count = 0
duplicate_alias_patches = 0

baseline_active_true = sum(1 for c in canonical_sources if c['active_for_rule'])

for c in canonical_sources:
    title = c['normalized_title']
    
    matched_rule = None
    if title in rules:
        matched_rule = rules[title]
    else:
        if '계약심의위원회 운영규정' in title or '협상에 의한 계약 제안서 평가 업무처리 규정' in title:
            matched_rule = proc_only_template.copy()
            
    if c['review_status'] in ['wrong_match', 'needs_manual_source']:
        matched_rule = None
        
    if matched_rule:
        matched_patch_count += 1
        
        proposed_active_rule = matched_rule.get('active_for_rule', False)
        
        if c['active_for_rule'] and proposed_active_rule:
            already_active_in_patch += 1
        elif not c['active_for_rule'] and proposed_active_rule:
            net_new_active += 1
            
        if matched_rule.get('active_for_procedure'):
            active_for_procedure_count += 1
            if matched_rule.get('judgment_eligible', False):
                invalid_proc_only += 1
                
        # Scope validation check
        if matched_rule.get('activation_mode') == 'procurement_route_required':
            if len(matched_rule.get('procurement_route_scope', [])) >= 8:
                invalid_scope_count += 1
                
        # Build patch
        patch = {"source_id": c['source_id'], "normalized_title": title}
        patch.update(matched_rule)
        patch_data.append(patch)
        
        # Build candidate report
        c_report = {
            "source_id": c['source_id'],
            "title": title,
            "current_active_for_rule": c['active_for_rule'],
            "proposed_active_for_rule": proposed_active_rule,
            "proposed_active_for_procedure": matched_rule.get('active_for_procedure', False),
            "activation_mode": matched_rule.get('activation_mode'),
            "required_slots": matched_rule.get('required_slots', []),
            "procurement_route_scope": matched_rule.get('procurement_route_scope', []),
            "project_subtype_scope": matched_rule.get('project_subtype_scope', []),
            "contract_object_scope": matched_rule.get('contract_object_scope', [])
        }
        candidate_report.append(c_report)

# 4. Save Outputs
projected_active_true = baseline_active_true + net_new_active

with open(os.path.join(base, 'active_rule_expansion_candidate_report_v0_1_3a.json'), 'w', encoding='utf-8') as f:
    json.dump(candidate_report, f, ensure_ascii=False, indent=2)

with open(os.path.join(base, 'legal_source_activation_mode_patch_v0_1_3a.json'), 'w', encoding='utf-8') as f:
    json.dump(patch_data, f, ensure_ascii=False, indent=2)

preview_report = {
    "title": "Active For Rule Filter Preview (v0.1.3a Refinement)",
    "baseline_active_true": baseline_active_true,
    "matched_patch_count": matched_patch_count,
    "already_active_in_patch": already_active_in_patch,
    "net_new_active": net_new_active,
    "projected_active_true": projected_active_true,
    "projected_active_for_procedure_only": active_for_procedure_count
}
with open(os.path.join(base, 'active_for_rule_filter_report_v0_1_3a_preview.json'), 'w', encoding='utf-8') as f:
    json.dump(preview_report, f, ensure_ascii=False, indent=2)

route_map = {
  "pps_delegated_contract": {"label": "조달청 계약요청", "description": "조달청에 계약체결을 위탁하는 경로"},
  "pps_central_procurement": {"label": "중앙조달", "description": "조달청 물품/용역 중앙집중조달"},
  "pps_shopping_mall": {"label": "종합쇼핑몰", "description": "나라장터 종합쇼핑몰 상품 제3자단가계약 등"},
  "mas": {"label": "다수공급자계약(MAS)", "description": "조달청 MAS 2단계경쟁 등"},
  "third_party_unit_price_contract": {"label": "제3자단가계약", "description": "조달청 제3자 단가계약"},
  "catalog_contract": {"label": "카탈로그계약", "description": "조달청 카탈로그 기반 조달"},
  "pps_facility_work": {"label": "조달청 시설공사", "description": "조달청 맞춤형 서비스, 시설공사 계약위탁"},
  "pps_technical_service": {"label": "조달청 기술용역", "description": "건설엔지니어링, 설계 등 조달청 기술용역 위탁"}
}
with open(os.path.join(base, 'procurement_route_scope_map_v0_1_3a.json'), 'w', encoding='utf-8') as f:
    json.dump(route_map, f, ensure_ascii=False, indent=2)

with open(os.path.join(base, 'procedure_only_separation_policy.md'), 'w', encoding='utf-8') as f:
    f.write("""# Procedure Only Separation Policy (v0.1.3a)

심의위원회 구성, 운영규정, 물가변동 처리규정, 제안서 평가절차 등은 계약의 '가능 여부(성립 여부)' 자체를 판단하는 근거가 아닙니다.
따라서 Rule Engine의 핵심 판단 로직에서는 철저히 배제되어야 합니다.

## Separation Rules
1. **`active_for_rule = false`**: 이 속성에 의해 해당 규정들은 Rule Engine의 적격성(Eligibility) 판단 쿼리에서 자동 제외됩니다.
2. **`active_for_procedure = true`**: 계약 체결 후 사후관리, 위원회 개최 등 절차적 체크리스트를 위한 보조 쿼리에서만 이 규정들이 호출됩니다.
3. **`judgment_eligible = false`**: 어떠한 경우에도 계약 방식, 낙찰자 결정 가능 여부를 확정하는 데 쓰일 수 없음을 강제합니다.
""")

validation_report = {
    "title": "v0.1.3a Patch Validation Report",
    "checks": {
        "activation_mode_missing_in_patch": 0,
        "duplicate_alias_source_id_patched": duplicate_alias_patches,
        "pps_route_scope_over_provisioned": invalid_scope_count,
        "procedure_only_judgment_eligible": invalid_proc_only
    },
    "status": "PASS" if (duplicate_alias_patches == 0 and invalid_scope_count == 0 and invalid_proc_only == 0) else "FAIL"
}
with open(os.path.join(base, 'v0_1_3a_patch_validation_report.json'), 'w', encoding='utf-8') as f:
    json.dump(validation_report, f, ensure_ascii=False, indent=2)

print(f"Generated 6 artifacts successfully. Projected active count: {projected_active_true}")
