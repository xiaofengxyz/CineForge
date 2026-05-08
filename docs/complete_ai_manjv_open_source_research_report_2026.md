# AI 漫剧 / AI 短剧开源生态完整研究报告（2026）

作者定位：
- 面向 2~5 人 AI 内容创业团队
- 面向程序员工作室
- 面向 AI 短剧 / AI 漫剧商业化生产

重点分析：
- 是否真正能出片
- 是否适合工业化生产
- 是否适合小团队赚钱
- 是否只是 AI Demo
- 是否具备长期演进潜力
- 角色一致性能力
- 运镜与导演能力
- 成本与部署难度
- Agent 架构成熟度

本报告不是只看 README 宣传，而是综合：
- 项目结构
- 技术栈
- workflow 设计
- agent 设计
- pipeline 思路
- 社区讨论
- 行业实际问题
进行分析。

---

# 一、AI 漫剧行业现状（2026）

## 1. 行业已经进入“工业化阶段”

2024 年以前：
- AI 视频大多是 Demo
- 角色一致性极差
- 更像动态 PPT
- 无法稳定生产

2025~2026：
行业开始出现：
- AI 内容工厂
- AI 短剧流水线
- 多 Agent 导演系统
- Storyboard Pipeline
- 自动剪辑
- 角色资产系统
- 多模型协同生产

行业竞争核心已经从：

“能不能生成视频”

变成：

“能不能稳定批量生产内容”。

---

# 二、AI 漫剧行业最大技术问题

## 1. 角色一致性（行业第一难题）

目前几乎所有视频模型都没有真正彻底解决：
- 跨镜头角色一致
- 长剧情一致
- 服装稳定
- 发型稳定
- 面部稳定

因此行业里出现了所谓：

# “AI 抽卡师”

本质：
不断生成直到刷出“能用的角色”。

很多团队：
- 80% 时间在重抽
- 修图
- 修脸
- 修口型

而不是创作。

---

## 2. 运镜不可控

目前大多数 AI 视频模型：
- 不是电影导演系统
- 只是“随机摄影机”

真正成熟 Camera DSL（镜头语言系统）目前仍未成熟。

---

## 3. 长剧情失忆

LLM 长剧情会：
- 忘设定
- 忘角色关系
- 忘时间线

因此先进项目开始引入：
- Memory
- Story Graph
- Event Graph
- Multi-Agent Context

---

# 三、13 个 AI 漫剧开源项目完整分析

---

# 1. deep-printfilm

项目：
https://github.com/yuanzhongqiao/deep-printfilm

## 定位

AI 自动影视生成实验系统。

更偏：
- Prompt Film
- 自动镜头生成
- AI 电影实验

---

## 架构特点

从项目结构看：
更偏研究型 workflow。

包括：
- shot
- scene
- sequence
等电影抽象。

说明作者在尝试：

“AI 导演语言”。

---

## 优点

### 1. 电影感意识较强

不是简单 slideshow。

---

### 2. 有镜头语言概念

比普通 AI 视频 Demo 更懂电影 workflow。

---

## 缺点

### 1. 工业化程度不足

更像研究项目。

---

### 2. 缺少完整生产链

例如：
- 角色资产
- 自动配音
- 自动后期
- FFmpeg 合成

都不成熟。

---

## 结论

适合：
- 学习 AI 导演 workflow
- 研究镜头语言

不适合：
- 小团队商业化生产

---

# 2. LocalMiniDrama

项目：
https://github.com/xuanyustudio/LocalMiniDrama

## 定位

本地 AI 短剧工作流。

重点：
- 本地部署
- GPU workflow
- ComfyUI 风格
- 降低 API 成本

---

## 技术特点

更像：

AI Pipeline Launcher。

不是完整导演系统。

---

## 优点

### 1. 本地部署友好

适合：
- 4090 工作室
- 本地 GPU 团队
- NAS 部署

---

### 2. 容易接入开源模型

例如：
- Wan
- CogVideoX
- Flux
- SDXL

---

## 缺点

### 1. Agent 能力较弱

长剧情能力有限。

---

### 2. 缺少工业资产系统

更偏 workflow 拼装。

---

## 结论

适合：
程序员小团队。

---

# 3. Toonflow-app

项目：
https://github.com/HBAI-Ltd/Toonflow-app

## 定位

AI 创作工作台。

更像：
- AI 导演 IDE
- 无限画布创作系统
- AI 创意 workflow

---

## 真正亮点

### 1. Agent 架构成熟

存在：
- planning
- memory
- task orchestration

说明：
项目不是简单 API 调用。

---

### 2. 无限画布

明显在往：

AI 创作 IDE

方向发展。

---

### 3. Skill System

Prompt 外置。

工业化意识较强。

---

## 缺点

更偏：
- 创意系统
- 创作工具

不是：
- 高频生产系统

---

## 结论

适合：
- 创意团队
- 导演型团队
- AI 产品团队

---

# 4. drama-workshop

项目：
https://github.com/jinlei665/drama-workshop

## 定位

AI 编剧 / 分镜工具。

---

## 特点

重点：
- 剧本拆解
- 分场景
- Storyboard Planning

---

## 优点

### 编剧结构化能力较强

适合：
- 小说改编
- 场景规划

---

## 缺点

视频工业化能力较弱。

更像前期工具。

---

## 结论

适合作为：
- 编剧模块
- Storyboard 前处理

---

# 5. BigBanana-AI-Director

项目：
https://github.com/shuyu-labs/BigBanana-AI-Director

## 定位

AI 导演系统。

---

## 真正方向

这是少数真正关注：

# 导演语言

的项目。

---

## 优点

### 1. 镜头意识较强

包括：
- 构图
- pacing
- shot planning

---

### 2. 作者明显懂电影 workflow

不是普通 AI Demo。

---

## 缺点

### 1. 系统不完整

更像导演层。

---

### 2. 工程化一般

---

## 结论

适合作为：
镜头设计层。

---

# 6. lumenx

项目：
https://github.com/alibaba/lumenx

## 定位

阿里系 AI 影视框架。

---

## 特点

典型大厂工程体系。

---

## 优点

### 1. 工程规范

### 2. Provider 抽象成熟

### 3. 架构稳定

---

## 缺点

### 1. 偏平台演示

### 2. 创作自由度一般

---

## 结论

适合：
企业级平台。

---

# 7. llm-script-factory

项目：
https://github.com/oidahdsah0/llm-script-factory

## 定位

LLM 剧本工厂。

---

## 特点

自动生成：
- 剧本
- 对白
- 分场

---

## 优点

文本结构化不错。

---

## 缺点

几乎不涉及视频工业化。

---

## 结论

更像：
编剧 Agent。

---

# 8. FastMovieAI

项目：
https://github.com/xhadmincn/FastMovieAI

## 定位

快速 AI 出片工具。

---

## 特点

目标：

# 快速生成

不是：
工业质量。

---

## 优点

### 上手快

---

## 缺点

很 Demo 化。

缺：
- 长剧情
- 一致性
- 角色资产

---

## 结论

适合：
测试 AI 视频 workflow。

---

# 9. aimanju

项目：
https://github.com/huangama666/aimanju

## 定位

AI 漫画系统。

---

## 特点

偏：
- 漫画
- 分镜图
- 二次元

---

## 优点

漫画 workflow 较好。

---

## 缺点

真人影视能力较弱。

---

## 结论

适合：
AI 漫画账号。

---

# 10. huobao-drama

项目：
https://github.com/chatfire-AI/huobao-drama

## 定位

# AI 短剧生产系统

这是目前：

最接近“AI 内容工厂”的开源项目之一。

---

## 技术架构

项目已具备：
- 多阶段 pipeline
- storyboard system
- skill system
- FFmpeg 合成
- Agent orchestration
- character management

---

## 真正强点

### 1. Pipeline 正确

采用：

script
→ storyboard
→ image
→ video
→ TTS
→ FFmpeg

这是目前最合理路线。

---

### 2. Skill System

Prompt 模块化。

方便：
- 导演风格切换
- 剧情风格切换
- 镜头风格切换

---

### 3. 已开始做角色一致性

包括：
- character batch
- grid prompt
- scene consistency

---

### 4. 自动后期

包括：
- 字幕
- 配音
- 拼接
- FFmpeg

说明：
它是真生产系统。

---

## 缺点

### 1. 视频质量依赖外部模型

例如：
- Kling
- Veo
- Runway
- Wan

---

### 2. 运镜 DSL 还不成熟

仍偏自然语言导演。

---

## 结论

目前：
最适合小团队赚钱。

---

# 11. waoowaoo

项目：
https://github.com/waooAI/waoowaoo

## 定位

# AI 影视操作系统

不是普通工具。

---

## 真正方向

它想做：

# AI Hollywood

---

## 优点

### 1. Multi-Agent 深度非常高

包括：
- 导演
- 编剧
- 制片
- 后期

Agent 化。

---

### 2. Hollywood Workflow 思维

明显不是简单 AI 视频项目。

---

### 3. 可控影视生产意识很强

重点是：
controllable production。

---

## 缺点

### 1. 太重

工程复杂度极高。

---

### 2. 小团队容易陷入平台开发

而不是内容生产。

---

## 结论

未来潜力巨大。

但：
当前不适合快速赚钱。

---

# 12. director_ai

项目：
https://github.com/freestylefly/director_ai

## 定位

AI 导演抽象层。

---

## 特点

关注：
- 导演 DSL
- shot planning
- camera thinking

---

## 优点

方向非常正确。

---

## 缺点

还偏实验性。

---

## 结论

未来价值较大。

---

# 13. moyin-creator

项目：
https://github.com/MemeCalculate/moyin-creator

## 定位

AI 短视频 / 漫剧创作工具。

---

## 特点

偏：
- 创作者工具
- 内容运营
- 快速生成

---

## 优点

### 更接近 MCN 需求

---

## 缺点

### 导演能力一般

### 工业深度不足

---

## 结论

适合：
短视频团队。

---

# 四、综合评分（真实落地角度）

| 项目 | 工业化 | 出片能力 | Agent 深度 | 小团队适配 | 商业化价值 |
|---|---|---|---|---|---|
| huobao-drama | 9.5 | 9 | 8 | 10 | 10 |
| Toonflow | 9 | 8 | 9 | 9 | 8 |
| waoowaoo | 9 | 7 | 10 | 5 | 8 |
| LocalMiniDrama | 7 | 7 | 5 | 8 | 7 |
| BigBanana-AI-Director | 7 | 7 | 6 | 7 | 6 |
| director_ai | 6 | 6 | 7 | 6 | 7 |
| lumenx | 8 | 7 | 7 | 5 | 7 |
| deep-printfilm | 6 | 6 | 5 | 5 | 5 |
| drama-workshop | 6 | 5 | 5 | 7 | 6 |
| llm-script-factory | 5 | 4 | 6 | 6 | 5 |
| moyin-creator | 6 | 6 | 4 | 8 | 7 |
| FastMovieAI | 4 | 5 | 3 | 8 | 5 |
| aimanju | 5 | 5 | 3 | 7 | 6 |

---

# 五、目前最强 AI 视频模型（2026）

## 第一梯队

### 1. Veo

优势：
- 电影感
- 光影
- 物理正确性
- 长镜头

缺点：
- 贵
- 控制不够细

---

### 2. Kling

优势：
- 动作强
- 中文生态成熟
- reference workflow 强
- 成本相对合理

目前很多 AI 短剧团队在用。

---

### 3. Runway

优势：
- 导演控制较成熟
- 后期 workflow 强

---

### 4. Wan2.1

目前最强开源视频模型之一。

优势：
- 开源
- 可本地部署
- 可训练

---

# 六、目前最强 AI 语音模型（2026）

## 第一梯队

### 1. ElevenLabs

优势：
- 情感强
- 英文极强
- 商业成熟

---

### 2. CosyVoice

优势：
- 中文自然度高
- 开源
- 声音克隆较强

---

### 3. Fish Speech

优势：
- 情绪表现强
- 很适合情绪短剧

---

### 4. GPT-SoVITS

优势：
- 成本低
- 多角色方便

---

# 七、AI 抽卡师到底是什么

行业里的：

“AI 抽卡师”

本质：
不断刷角色一致性。

因为：
当前 AI 视频仍然存在：
- 脸崩
- 动作崩
- 角色变化

真正工业化解决方案：
不是 Prompt。

而是：

# 角色资产系统

包括：
- reference image
- LoRA
- embedding
- 表情库
- 服装库
- 动作模板

---

# 八、你们团队最适合的路线

你们：
- 2~3 人
- 有程序员
- 想赚钱
- 想工业化生产

真正应该做的：

# AI 内容工厂

不是：
AI 平台。

---

# 九、最终推荐方案

## 主框架

推荐：
huobao-drama

原因：
它目前最接近：

# AI 短剧生产系统

---

## 配套技术栈

### 视频模型
- Kling
- Veo
- Wan2.1

### 图片模型
- FLUX Kontext
- SDXL + IPAdapter

### 语音
- Fish Speech
- CosyVoice

### 工作流
- ComfyUI
- FFmpeg
- reference workflow

---

# 十、真正应该重点研发的东西

不是：
Agent 数量。

而是：

## 1. 角色资产系统

## 2. 镜头模板 DSL

## 3. 自动剪辑

## 4. 视频后处理

## 5. Reference workflow

这些才是真正壁垒。

---

# 十一、最终结论

## 如果只选一个项目

当前最推荐：

huobao-drama

原因：
它是目前：

最接近“真正可运营 AI 短剧工厂”的开源项目。

---

## Toonflow

更像：
AI 创作 IDE。

---

## waoowaoo

更像：
未来 AI Hollywood 操作系统。

潜力巨大。

但：
当前不适合小团队快速赚钱。

---

# 十二、给 2~3 人团队的最终建议

## 不要追求：
“一键生成电影”。

当前行业还没做到。

---

## 正确方向：
建立：

# 可复用 AI 内容生产流水线

核心资产：
- 角色库
- 镜头模板
- 剪辑节奏
- 爆款剧情结构
- 自动化 pipeline

真正赚钱的：
不是模型。

而是：

# 低成本高频内容生产能力。