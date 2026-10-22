---
name: asset-correlation
description: "资产关联：域名↔IP↔C 段↔证书↔服务的图谱化。"
version: 1.4.2
author: YuJunZhiXue (dsh-purge), Hermes plugin port
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [redteam, recon, security]
    category: security
    related_skills: []
---

# asset-correlation

移植自 dsh-purge 红队技能库（原文照录，仅补齐 Hermes 头部元数据与路径）。

## When to Use

信息收集阶段性收口，需要形成资产关系视图时

## Procedure

### 关联规则
- 域名解析 → `resolves` 边（domain → asset）
- C 段归属 → `contains` 边（segment → asset）
- 端口开放 → `exposes` 边（asset → port）
- 证书 SAN 共享 → `shares_cert` 边

### 落库要求
通过 redteam_asset_link 写入 edge 表；重复关系幂等。
