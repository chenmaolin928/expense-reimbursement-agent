# Task 6 Report: JSON to DB Migration Script

## 文件

- `backend/scripts/migrate_json_to_db.py` — 迁移脚本
- `backend/scripts/__init__.py` — 包初始化文件

## 验证

```
# 导入验证
$ python -c "from scripts.migrate_json_to_db import migrate; print('import OK')"
import OK

# 首次运行 — 迁移成功
$ python scripts/migrate_json_to_db.py
  OK default: policy_id=1, version_id=1
Done. Migrated: 1, Skipped: 0

# 二次运行 — 幂等性验证
$ python scripts/migrate_json_to_db.py
  SKIP default: already has published policy (id=1)
Done. Migrated: 0, Skipped: 1
```

## 迁移逻辑

1. 读取 `backend/policies/*.json` 所有 JSON 文件
2. 文件名（去掉 .json）作为 enterprise 名称
3. 检查数据库中是否已有该 enterprise 的 PUBLISHED 状态 Policy（幂等）
4. 不存在则创建 Policy + PolicyVersion（status=PUBLISHED），设置 current_version_id
5. JSON 内容完整存入 `policy_json` 列

## 数据流

```
policies/default.json  →  Policy(enterprise="default", status=PUBLISHED)
                            └─ PolicyVersion(version_number=1, policy_json={…})
                                  policy.current_version_id = version.id
```
