# 📁 已归档 — 中文文档快照，非当前状态

这里是开发期维护的中文文档副本，**已于 2026-07-29 停止维护**。保留作为历史记录，不再更新。

**当前状态一律以 `docs/en/` 为准。**

## 为什么停掉

这套中文文档是一份需要人工同步的副本，而它已经和英文版各自漂移了：

- `Repository_Structure_ch.md` 还在描述早已删除的 Index / Query / Compare 三页前端 —— 这会**主动误导**读者。
- `Technical_Design_ch.md` 有 27K，而它对照的英文版只有 8K。三倍体量说明两边是各自独立演化的，谁也不能算权威。
- `Agentic_Workflow_ch.md` 只有 2K，英文版 7K —— 不是过期，是从来没译完。
- `Honesty_Constraints.md`（项目最有辨识度的一份文档）从来没有中文版。

八份半新半旧的文档，比一份都没有更糟：读者无法判断手上这份是不是当前的。

## 唯一保留的中文文档

[`docs/ch/Final_Report_ch.md`](../../ch/Final_Report_ch.md) 仍在维护，理由是结构性的而非偏好：它是唯一包含**生成块**的中文文档，数字由 `scripts/sync_eval_artifacts.py` 从 `results/eval-real/` 直接写入，`make check` 会在漂移时失败。也就是说它的关键内容**不可能**悄悄过期。其余全是手工散文。

它开头标注了"英文版为权威"。

## 目录

| 文件 | 对应的当前英文文档 |
|---|---|
| `Technical_Design_ch.md` | [`docs/en/Technical_Design.md`](../../en/Technical_Design.md) |
| `Database_ch.md` | 已并入 [`Technical_Design.md`](../../en/Technical_Design.md)（设计理由）与 [`Operations.md`](../../en/Operations.md)（运维坑） |
| `Repository_Structure_ch.md` | 已并入 [`Technical_Design.md`](../../en/Technical_Design.md) 的 Repository Layout 一节 |
| `Outstanding_Work_ch.md` | 已并入 [`Final_Report.md`](../../en/Final_Report.md) 的 Outstanding Work 一节 |
| `Sidecar_Smoke_ch.md` | [`docs/en/Operations.md`](../../en/Operations.md) |
| `Project_Plan_ch.md` | 已归档（项目已完成，里程碑与风险登记表属于历史） |
| `Agentic_Workflow_ch.md` | [`docs/en/Agentic_Workflow.md`](../../en/Agentic_Workflow.md) |
