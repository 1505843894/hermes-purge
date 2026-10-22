---
name: passive-recon
description: "被动信息收集：不接触目标主机，仅使用公开数据源。"
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

# passive-recon

移植自 dsh-purge 红队技能库（原文照录，仅补齐 Hermes 头部元数据与路径）。

## When to Use

需要在不暴露自身的情况下收集目标资产情报时

## Procedure

### 数据源
- 证书透明日志（crt.sh）：`curl -s "https://crt.sh/?q=%25.<domain>&output=json" | jq -r '.[].name_value' | sort -u`
- DNS 记录：`dig +short <domain> A/AAAA/MX/TXT/NS`
- whois：注册人、网段、ASN
- 搜索引擎与代码托管平台：泄露的子域、密钥、内部地址
- 公开端口测绘数据（Shodan/Censys/FOFA 等，需授权 API）

### 落库要求
每条发现调用 redteam_asset_upsert，provenance 固定为 `passive`，tool 记录具体数据源。


