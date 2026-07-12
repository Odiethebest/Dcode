# H1 结论

## 结论

当前 committed evaluation suite 下，**H1 仍未被支持**。

## 依据

题集信息：

- repository: `requests`
- size: 16 questions
- focus: L1 / L2 / L3 curated code-understanding tasks

验收规则：

- B4 需要在主要检索指标上优于 B0 到 B3；
- L2 和 L3 是 H1 的重点；
- groundedness 需要保持在可接受水平；
- 结论必须来自 committed result files，而不是人工预期。

## 当前结果

当前 `results/eval-suite/` 结果显示：

- B4 没有在 L2 或 L3 上稳定超过 B2/B3；
- groundedness 达到当前检查要求；
- retrieval uplift 不足以支持 H1。

因此，正确结论是 H1 unsupported。

## 解释

这个结论只说明当前记录的评测结果不足以支持 H1。它不否定系统架构，也不否定 graph 和 hybrid retrieval 的潜在价值。

当前结果受以下因素影响：

- 题集规模偏小；
- baseline path 需要进一步隔离；
- real embedding/reranker sidecar 尚未完整刷新 committed eval；
- graph v1 覆盖范围有限。

## 后续判断条件

只有在完成以下工作后，才应更新 H1 结论：

1. 用 Jina v2 embedding 和 BGE reranker 重新索引目标仓库；
2. 使用同一配置重新跑完整 eval suite；
3. 确认 B1/B2/B3/B4 baseline path 独立；
4. 扩展或审查题集；
5. 将新结果提交到 `results/`；
6. 根据新结果更新本文档。
