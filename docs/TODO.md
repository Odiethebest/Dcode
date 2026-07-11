# Dcode TODO

> 当前仓库状态基于 **2026-07-11** 的代码审查与本地验证，不再保留早期 M0 skeleton 清单。
>
> 关联文档：[README.md](../README.md)、[DESIGN.md](DESIGN.md)、[PLAN.md](PLAN.md)、[final_report.md](final_report.md)、[h1_decision.md](h1_decision.md)。
>
> 历史执行日志已归档到 [archive/roadmap.md](archive/roadmap.md)。新的剩余工作只在本文维护。

---

## 当前状态

- 已完成：索引管线、内部 retrieval API、LangGraph SSE、8 个 agent 工具、groundedness、frontend `Index / Query / Compare`、评测 harness、embedding sidecar、reranker sidecar、production compose 打包。
- 已验证：
  - `make check`（2026-07-11）
  - `make frontend-build`
  - `make eval-smoke`
- 未在本轮重新验证：
  - `make migrate`
  - real embedding/reranker sidecar 下的完整 re-index + eval suite
- 当前 H1 结论：**unsupported**
- 当前外部部署状态：`dcode.odieyang.com` 在 2026-07-11 **未解析**

---

## 剩余高优先级工作

### 1. 检索质量

- [x] 接通真实 chunk embedding 写入客户端，支持通过 HTTP sidecar 替换 `StubEmbeddingClient`
- [x] 接通 query-side embedding，支持真实 dense retrieval
- [x] 接通真实 reranker，支持通过 HTTP sidecar 替换 identity rerank
- [x] 扩展 graph beyond module imports：已加入 best-effort intra-repo `calls`
- [ ] 用真实 embedding/reranker 配置重新索引目标 repo，并记录可复现运行参数
- [ ] 继续扩展 graph：richer references / inheritance / 更复杂属性链调用

### 2. 评测完整性

- [ ] 接通 Judge / pairwise 评分链路
- [ ] 把当前 16 题 `requests` 题集扩到更稳健的规模
- [ ] 为 `B0/B1` 跑出与 `B2/B3/B4` 同口径的稳定结果
- [ ] 为 B1/B2/B3/B4 拆出真正独立的 retrieval 路径，避免全部复用 `/internal/search`
- [ ] 用 real embedding/reranker 重新生成 `results/eval-suite/`
- [ ] 同步更新 frontend `evalSnapshot.ts`，确保展示数字与 `results/` 一致

### 3. 外部上线

- [ ] 为 `dcode.odieyang.com` 配置真实 DNS
- [ ] 在真实公网主机上应用 `.env.production`
- [ ] 明确 production compose 是否包含 embedding/reranker sidecar，或记录外部模型服务依赖
- [ ] 运行 production compose 并做公网 smoke

### 4. 后续增强

- [ ] 在检索质量改善后，再评估是否接入 LLM planner
- [ ] 在检索质量改善后，再评估是否接入 LLM synthesis
- [ ] 若前端类型漂移成为维护成本，再接入 OpenAPI 类型生成
- [ ] 若评测结果继续迭代，让 `Compare` 页从版本化结果快照生成展示数据

---

## 已知实现边界

- [ ] 默认环境仍是 `EMBEDDING_MODEL=stub`
- [ ] 当前 graph 是 v1：definitions + module import edges + best-effort intra-repo call edges
- [ ] 当前 agent planner / synthesize 为规则与模板；已支持规则化多步循环，但不是 LLM planner
- [ ] 当前 H1 判定只基于已落地指标，不含 Judge / pairwise，且尚未使用 real embedding/reranker 路径重新评测

---

## 清理建议

- [ ] 若继续迭代评测，将 `results/` 快照整理成明确命名的版本化 fixture
- [ ] 若继续维护，考虑把 production compose 的公网 smoke 脚本化进 CI/CD
