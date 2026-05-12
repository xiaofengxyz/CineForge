import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Col,
  Collapse,
  Empty,
  Form,
  Input,
  InputNumber,
  Progress,
  Row,
  Select,
  Skeleton,
  Space,
  Statistic,
  Steps,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import {
  CheckCircleOutlined,
  ClusterOutlined,
  CloudDownloadOutlined,
  ExperimentOutlined,
  FileDoneOutlined,
  PictureOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SaveOutlined,
  SettingOutlined,
  VideoCameraOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { StudioChaptersService, type ChapterRead } from '../../../services/generated'
import {
  collectFilmEngineStockAssets,
  createFilmEngineRetryTask,
  evaluateFilmEngineShotQA,
  getFilmEngineApiBaseURL,
  getFilmEngineConfig,
  getFilmEngineSeriesIndex,
  getFilmEngineStageIndex,
  updateFilmEngineConfig,
  type FilmEngineConfig,
  type FilmEngineQAReport,
  type FilmEngineRenderRequest,
  type FilmEngineRetryRequest,
  type FilmEngineSeriesChapter,
  type FilmEngineSeriesIndex,
  type FilmEngineStage,
  type FilmEngineStageIndex,
  type FilmEngineStockAsset,
  type FilmEngineStockAssetCollectResult,
} from '../../../services/filmEngine'

const { Text, Paragraph } = Typography

type FilmEngineDashboardProps = {
  embedded?: boolean
  projectId?: string
}

const referenceModeOptions: { value: FilmEngineConfig['reference_mode']; label: string }[] = [
  { value: 'first', label: '首帧' },
  { value: 'last', label: '尾帧' },
  { value: 'key', label: '关键帧' },
  { value: 'first_last', label: '首帧 + 尾帧' },
  { value: 'first_last_key', label: '首帧 + 尾帧 + 关键帧' },
  { value: 'text_only', label: '纯文本' },
]

const statusTag = (status: string) => {
  if (status === 'done') {
    return (
      <Tag color="success" icon={<CheckCircleOutlined />}>
        Done
      </Tag>
    )
  }
  return (
    <Tag color="warning" icon={<WarningOutlined />}>
      Pending
    </Tag>
  )
}

const shorten = (value: string, limit = 96) => {
  if (value.length <= limit) return value
  return `${value.slice(0, limit)}...`
}

const metricText = (metrics?: Record<string, unknown> | null) => {
  if (!metrics) return '-'
  const entries = Object.entries(metrics)
  if (!entries.length) return '-'
  return entries.map(([key, value]) => `${key}: ${String(value)}`).join(' · ')
}

function getErrorDescription(err: unknown) {
  const maybe = err as { code?: string; message?: string; response?: { data?: { message?: string } } }
  const apiBase = getFilmEngineApiBaseURL()
  const serverMessage = maybe.response?.data?.message
  if (serverMessage) return serverMessage
  if (maybe.code === 'ERR_NETWORK' || maybe.message?.includes('Network Error')) {
    return `无法连接后端 API：${apiBase}。请确认后端已启动：cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000。`
  }
  return maybe.message || 'Film Engine 状态加载失败'
}

function QAReportList({ reports }: { reports: FilmEngineQAReport[] }) {
  if (!reports.length) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无 QA 报告" />
  return (
    <div className="space-y-3">
      {reports.map((report) => (
        <div key={report.shot_id} className="rounded border border-solid border-gray-200 p-3">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <Text strong>{report.shot_id}</Text>
            <Space>
              <Tag color={report.passed ? 'success' : 'error'}>
                {report.passed ? 'Passed' : 'Needs Retry'}
              </Tag>
              <Text type="secondary">score {report.score.toFixed(2)}</Text>
            </Space>
          </div>
          <div className="mt-2 space-y-1">
            <Text type="secondary" className="text-xs">
              {metricText(report.metrics)}
            </Text>
            {report.issues.length ? (
              report.issues.map((issue) => (
                <div key={`${report.shot_id}-${issue.code}`} className="text-sm text-gray-700">
                  <Tag color={issue.severity === 'high' ? 'error' : 'warning'}>{issue.code}</Tag>
                  {issue.message}
                </div>
              ))
            ) : (
              <Text type="secondary">无阻断问题</Text>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

function RetryList({ retries }: { retries: FilmEngineRetryRequest[] }) {
  if (!retries.length) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无重试请求" />
  return (
    <div className="space-y-3">
      {retries.map((retry) => (
        <div key={retry.shot_id} className="rounded border border-solid border-gray-200 p-3">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <Text strong>{retry.shot_id}</Text>
            <Space wrap>
              {retry.reason_codes.map((code) => (
                <Tag key={code} color="processing">
                  {code}
                </Tag>
              ))}
            </Space>
          </div>
          <Paragraph className="mt-2 mb-0 text-sm" ellipsis={{ rows: 2, expandable: true, symbol: '展开' }}>
            {retry.prompt}
          </Paragraph>
          <Text type="secondary">{metricText(retry.parameters)}</Text>
        </div>
      ))}
    </div>
  )
}

export default function FilmEngineDashboard({ embedded = false, projectId }: FilmEngineDashboardProps) {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [data, setData] = useState<FilmEngineStageIndex | null>(null)
  const [series, setSeries] = useState<FilmEngineSeriesIndex | null>(null)
  const [config, setConfig] = useState<FilmEngineConfig | null>(null)
  const [chapters, setChapters] = useState<ChapterRead[]>([])
  const [selectedChapterId, setSelectedChapterId] = useState<string | undefined>(
    searchParams.get('chapter') || undefined,
  )
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [qaEvaluatingShotId, setQaEvaluatingShotId] = useState<string | null>(null)
  const [retryingShotId, setRetryingShotId] = useState<string | null>(null)
  const [assetCollecting, setAssetCollecting] = useState(false)
  const [stockAssetBatch, setStockAssetBatch] = useState<FilmEngineStockAssetCollectResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [form] = Form.useForm<FilmEngineConfig>()

  useEffect(() => {
    let cancelled = false
    if (!projectId) {
      setChapters([])
      setSelectedChapterId(undefined)
      return () => {
        cancelled = true
      }
    }
    StudioChaptersService.listChaptersApiV1StudioChaptersGet({
      projectId,
      page: 1,
      pageSize: 100,
      order: 'index',
      isDesc: false,
    })
      .then((res) => {
        if (cancelled) return
        const items = res.data?.items ?? []
        setChapters(items)
        const current = searchParams.get('chapter')
        if (!current && items[0]?.id) setSelectedChapterId(items[0].id)
      })
      .catch(() => {
        if (!cancelled) setChapters([])
      })
    return () => {
      cancelled = true
    }
  }, [projectId, searchParams])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    if (!projectId) setSeries(null)
    try {
      const [stageIndex, projectConfig] = await Promise.all([
        getFilmEngineStageIndex({ projectId, chapterId: selectedChapterId }),
        projectId ? getFilmEngineConfig(projectId) : Promise.resolve(null),
      ])
      const seriesIndex = projectId ? await getFilmEngineSeriesIndex(projectId) : null
      const effectiveConfig = projectConfig ?? stageIndex.summary.metadata.config ?? null
      setData(stageIndex)
      setSeries(seriesIndex)
      setConfig(effectiveConfig)
      if (effectiveConfig) form.setFieldsValue(effectiveConfig)
      if (projectId && !selectedChapterId && stageIndex.chapter.id) {
        setSelectedChapterId(stageIndex.chapter.id)
      }
    } catch (err) {
      setError(getErrorDescription(err))
    } finally {
      setLoading(false)
    }
  }, [form, projectId, selectedChapterId])

  useEffect(() => {
    void load()
  }, [load])

  const updateSelectedChapter = (value: string) => {
    setSelectedChapterId(value)
    if (embedded) {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          next.set('tab', 'film-engine')
          next.set('chapter', value)
          return next
        },
        { replace: true },
      )
    }
  }

  const saveConfig = async () => {
    if (!projectId) return
    const values = await form.validateFields()
    setSaving(true)
    try {
      const next = await updateFilmEngineConfig(projectId, values)
      setConfig(next)
      form.setFieldsValue(next)
      message.success('Film Engine 配置已保存')
      await load()
    } catch (err) {
      message.error(getErrorDescription(err))
    } finally {
      setSaving(false)
    }
  }

  const summary = data?.summary
  const doneCount = data?.stages.filter((stage) => stage.status === 'done').length ?? 0
  const workflowDoneCount = data?.workflow_stages.filter((stage) => stage.status === 'done').length ?? 0
  const stagePercent = data?.stages.length ? Math.round((doneCount / data.stages.length) * 100) : 0
  const workflowPercent = data?.workflow_stages.length ? Math.round((workflowDoneCount / data.workflow_stages.length) * 100) : 0
  const retryCount = summary?.retry_requests.length ?? 0
  const renderCount = summary?.render_requests.length ?? 0
  const qaPassed = summary?.qa.passed ?? false
  const nextAction = summary?.metadata.next_action
  const retryByShotId = useMemo(() => {
    const map = new Map<string, FilmEngineRetryRequest>()
    const retryRequests = summary?.retry_requests ?? []
    retryRequests.forEach((retry) => {
      map.set(retry.shot_id, retry)
    })
    return map
  }, [summary?.retry_requests])

  const goNext = () => {
    if (!projectId) {
      navigate('/projects')
      return
    }
    const chapterId = selectedChapterId || data?.chapter.id
    const actionKey = nextAction?.key
    if (actionKey === 'create_chapter') {
      navigate(`/projects/${projectId}?tab=chapters&create=1`)
      return
    }
    if (!chapterId) {
      navigate(`/projects/${projectId}?tab=chapters`)
      return
    }
    if (actionKey === 'extract_shots') {
      navigate(`/projects/${projectId}/chapters/${chapterId}/shots`)
      return
    }
    if (actionKey === 'final_export') {
      navigate(`/projects/${projectId}/editor`)
      return
    }
    navigate(`/projects/${projectId}/chapters/${chapterId}/studio`)
  }

  const evaluateShotQA = useCallback(
    async (shotId: string) => {
      setQaEvaluatingShotId(shotId)
      try {
        const result = await evaluateFilmEngineShotQA(shotId)
        const metricSummary = metricText(result.metrics)
        message.success(`Film Visual QA 已写入：${metricSummary}`)
        await load()
      } catch (err) {
        message.error(getErrorDescription(err))
      } finally {
        setQaEvaluatingShotId(null)
      }
    },
    [load],
  )

  const createRetryTask = useCallback(
    async (shotId: string) => {
      if (!projectId) return
      setRetryingShotId(shotId)
      try {
        const result = await createFilmEngineRetryTask({
          projectId,
          shotId,
          chapterId: selectedChapterId || data?.chapter.id,
        })
        message.success(`Retry 视频任务已创建：${result.task_id}`)
        await load()
      } catch (err) {
        message.error(getErrorDescription(err))
      } finally {
        setRetryingShotId(null)
      }
    },
    [data?.chapter.id, load, projectId, selectedChapterId],
  )

  const collectStockAssets = useCallback(async () => {
    setAssetCollecting(true)
    try {
      const result = await collectFilmEngineStockAssets({
        projectId,
        chapterId: selectedChapterId || data?.chapter.id,
        imageCount: 4,
        videoCount: 2,
        persist: !!projectId,
      })
      setStockAssetBatch(result)
      message.success(
        result.persisted
          ? `已采集 ${result.item_count} 个基础素材，新增 ${result.created_file_count} 个文件`
          : `已采集 ${result.item_count} 个基础素材`,
      )
      if (result.persisted) await load()
    } catch (err) {
      message.error(getErrorDescription(err))
    } finally {
      setAssetCollecting(false)
    }
  }, [data?.chapter.id, load, projectId, selectedChapterId])

  const stageColumns: ColumnsType<FilmEngineStage> = useMemo(
    () => [
      {
        title: '阶段',
        dataIndex: 'title',
        width: 190,
        render: (_, stage) => (
          <div className="min-w-0">
            <div className="font-medium">{stage.title}</div>
            <Text type="secondary" className="text-xs">
              {stage.id}
            </Text>
          </div>
        ),
      },
      { title: 'Owner', dataIndex: 'owner', width: 140 },
      { title: '状态', dataIndex: 'status', width: 110, render: statusTag },
      {
        title: '证据',
        dataIndex: 'evidence',
        render: (_, stage) => (
          <div className="space-y-1">
            <div>{stage.evidence}</div>
            <Text type="secondary" className="text-xs">
              {metricText(stage.metrics)}
            </Text>
          </div>
        ),
      },
      {
        title: '核心产物',
        dataIndex: 'artifacts',
        width: 260,
        render: (artifacts?: string[] | null) => (
          <Space size={[4, 4]} wrap>
            {(artifacts ?? []).slice(0, 3).map((artifact) => (
              <Tag key={artifact}>{artifact}</Tag>
            ))}
          </Space>
        ),
      },
    ],
    [],
  )

  const renderColumns: ColumnsType<FilmEngineRenderRequest> = useMemo(
    () => [
      { title: 'Shot', dataIndex: 'shot_id', width: 120 },
      { title: 'Runtime', width: 160, render: (_, item) => `${item.provider} / ${item.model}` },
      { title: 'References', width: 120, render: (_, item) => item.references.length },
      { title: 'Prompt', dataIndex: 'prompt', render: (prompt: string) => <Text>{shorten(prompt)}</Text> },
      { title: 'Output', dataIndex: 'output_path', width: 220, render: (value: string) => <Text type="secondary">{value}</Text> },
      {
        title: '操作',
        width: 220,
        render: (_, item) => (
          <Space wrap>
            <Button
              size="small"
              icon={<ExperimentOutlined />}
              loading={qaEvaluatingShotId === item.shot_id}
              onClick={() => void evaluateShotQA(item.shot_id)}
            >
              Film QA
            </Button>
            {projectId && retryByShotId.has(item.shot_id) ? (
              <Button
                size="small"
                type="primary"
                icon={<PlayCircleOutlined />}
                loading={retryingShotId === item.shot_id}
                onClick={() => void createRetryTask(item.shot_id)}
              >
                Retry
              </Button>
            ) : null}
          </Space>
        ),
      },
    ],
    [createRetryTask, evaluateShotQA, projectId, qaEvaluatingShotId, retryByShotId, retryingShotId],
  )

  const seriesColumns: ColumnsType<FilmEngineSeriesChapter> = useMemo(
    () => [
      {
        title: '章节',
        dataIndex: 'title',
        width: 220,
        render: (_, item) => (
          <div className="min-w-0">
            <div className="font-medium">第{item.index}集 · {item.title}</div>
            <Text type="secondary" className="text-xs">
              {item.id}
            </Text>
          </div>
        ),
      },
      {
        title: '生产进度',
        width: 180,
        render: (_, item) => (
          <Space direction="vertical" size={2}>
            <Text>镜头 {item.generated_video_count}/{item.plannable_shot_count}</Text>
            <Progress
              percent={item.plannable_shot_count ? Math.round((item.generated_video_count / item.plannable_shot_count) * 100) : 0}
              showInfo={false}
              size="small"
            />
          </Space>
        ),
      },
      {
        title: '九阶段',
        width: 120,
        render: (_, item) => `${item.stage_done_count}/${item.stage_total}`,
      },
      {
        title: 'QA / Retry',
        width: 160,
        render: (_, item) => (
          <Space size={[4, 4]} wrap>
            <Tag color={item.qa_passed ? 'success' : item.qa_report_count ? 'warning' : 'default'}>
              QA {item.qa_report_count}
            </Tag>
            <Tag color={item.retry_count ? 'processing' : 'default'}>Retry {item.retry_count}</Tag>
          </Space>
        ),
      },
      {
        title: '下一步',
        dataIndex: 'next_action',
        render: (_, item) => item.next_action?.hint ?? '-',
      },
    ],
    [],
  )

  const stockAssetColumns: ColumnsType<FilmEngineStockAsset> = useMemo(
    () => [
      {
        title: '预览',
        dataIndex: 'thumbnail_url',
        width: 110,
        render: (_, item) => (
          <a href={item.source_url} target="_blank" rel="noreferrer" className="block">
            <div className="relative h-[58px] w-[92px] overflow-hidden rounded border border-solid border-gray-200 bg-gray-50">
              <img src={item.thumbnail_url || item.source_url} alt={item.title} className="h-full w-full object-cover" />
              {item.media_type === 'video' ? (
                <VideoCameraOutlined className="absolute bottom-1 right-1 rounded bg-black/60 p-1 text-white" />
              ) : null}
            </div>
          </a>
        ),
      },
      {
        title: '类型',
        dataIndex: 'media_type',
        width: 110,
        render: (value: string) => (
          <Tag icon={value === 'video' ? <VideoCameraOutlined /> : <PictureOutlined />} color={value === 'video' ? 'purple' : 'blue'}>
            {value === 'video' ? '视频' : '图片'}
          </Tag>
        ),
      },
      {
        title: '素材',
        dataIndex: 'title',
        render: (_, item) => (
          <Space direction="vertical" size={0} className="min-w-0">
            <a href={item.source_url} target="_blank" rel="noreferrer">
              {shorten(item.title, 72)}
            </a>
            <Text type="secondary" className="text-xs">
              {item.file_id ?? item.provider}
            </Text>
          </Space>
        ),
      },
      {
        title: '许可证页',
        dataIndex: 'license_page_url',
        width: 160,
        render: (value: string) => (
          <a href={value} target="_blank" rel="noreferrer">
            Commons
          </a>
        ),
      },
    ],
    [],
  )

  if (loading && !data) {
    return (
      <div className="h-full overflow-auto p-4">
        <Skeleton active paragraph={{ rows: 10 }} />
      </div>
    )
  }

  return (
    <div className="h-full overflow-auto p-4 space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <div className="text-xl font-semibold text-gray-900">AI Film Engine</div>
          <div className="text-sm text-gray-500">
            {summary ? `${summary.project.title} · ${summary.chapter.title}` : '工业级 AI 漫剧闭环状态'}
          </div>
        </div>
        <Space wrap>
          {projectId && chapters.length > 0 ? (
            <Select
              value={selectedChapterId}
              style={{ width: 220 }}
              options={chapters.map((chapter) => ({
                value: chapter.id,
                label: `第${chapter.index}章 · ${chapter.title}`,
              }))}
              onChange={updateSelectedChapter}
            />
          ) : null}
          <Button
            type="primary"
            icon={<CloudDownloadOutlined />}
            loading={assetCollecting}
            onClick={() => void collectStockAssets()}
          >
            采集基础素材
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => void load()} loading={loading}>
            刷新
          </Button>
        </Space>
      </div>

      {error ? (
        <Alert
          type="error"
          showIcon
          message="Film Engine 状态不可用"
          description={error}
          action={<Button onClick={() => void load()}>重新连接</Button>}
        />
      ) : null}

      {data ? (
        <>
          <Alert
            type={data.all_stages_done ? 'success' : 'warning'}
            showIcon
            message={data.all_stages_done ? '九阶段证据已齐备' : '当前上下文仍有待补阶段'}
            description={
              projectId
                ? nextAction?.hint ?? 'Film Engine 已接入当前项目，可在这里配置运行时、QA 和 Retry，并跳转到下一步生成流程。'
                : '无项目上下文时展示内置九阶段验收样例；真实生产请从项目工作台进入 Film Engine。'
            }
            action={
              <Button type="primary" icon={<PlayCircleOutlined />} onClick={goNext}>
                {nextAction?.label ?? (projectId ? '继续流程' : '进入项目')}
              </Button>
            }
          />

          <Row gutter={[16, 16]}>
            <Col xs={24} sm={12} lg={6}>
              <Card size="small" className="h-full">
                <Statistic title="九阶段证据" value={doneCount} suffix={`/ ${data.stages.length}`} prefix={<ClusterOutlined />} />
                <Progress percent={stagePercent} showInfo={false} size="small" className="mt-2" />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card size="small" className="h-full">
                <Statistic title="生产闭环" value={workflowDoneCount} suffix={`/ ${data.workflow_stages.length}`} prefix={<FileDoneOutlined />} />
                <Progress percent={workflowPercent} showInfo={false} size="small" className="mt-2" />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card size="small" className="h-full">
                <Statistic title="Render Requests" value={renderCount} prefix={<FileDoneOutlined />} />
              </Card>
            </Col>
            <Col xs={24} sm={12} lg={6}>
              <Card size="small" className="h-full">
                <Statistic title="Retry Requests" value={retryCount} prefix={<ExperimentOutlined />} />
                <Text type="secondary">{qaPassed ? 'QA passed' : retryCount ? 'Retry ready' : '等待 QA'}</Text>
              </Card>
            </Col>
          </Row>

          {stockAssetBatch ? (
            <Card
              size="small"
              title={`基础素材采集 · ${shorten(stockAssetBatch.query, 56)}`}
              extra={<Tag color={stockAssetBatch.persisted ? 'success' : 'default'}>{stockAssetBatch.persisted ? '已写入项目' : '预览'}</Tag>}
            >
              <Table
                rowKey={(item) => item.file_id || item.id}
                size="small"
                columns={stockAssetColumns}
                dataSource={stockAssetBatch.items}
                pagination={false}
                scroll={{ x: 720 }}
              />
            </Card>
          ) : null}

          {projectId && series ? (
            <Card size="small" title="多集生产总览">
              <Row gutter={[16, 16]} className="mb-3">
                <Col xs={12} md={6}>
                  <Statistic title="章节" value={series.episode_count} />
                </Col>
                <Col xs={12} md={6}>
                  <Statistic title="可规划镜头" value={series.totals.plannable_shot_count} />
                </Col>
                <Col xs={12} md={6}>
                  <Statistic title="已生成视频" value={series.totals.generated_video_count} />
                </Col>
                <Col xs={12} md={6}>
                  <Statistic title="Retry" value={series.totals.retry_count} />
                </Col>
              </Row>
              <Alert
                className="mb-3"
                type={series.all_chapters_done ? 'success' : 'info'}
                showIcon
                message={series.all_chapters_done ? '多集闭环已完成' : '多集闭环进行中'}
                description={series.next_action?.hint ?? '按章节顺序完成分镜、资产、生成、QA、Retry 与导出。'}
              />
              <Table
                rowKey="id"
                size="small"
                columns={seriesColumns}
                dataSource={series.chapters}
                pagination={false}
                scroll={{ x: 900 }}
              />
            </Card>
          ) : null}

          {projectId ? (
            <Card
              size="small"
              title={
                <Space>
                  <SettingOutlined />
                  <span>Film Engine 运行配置</span>
                </Space>
              }
              extra={
                <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={() => void saveConfig()}>
                  保存配置
                </Button>
              }
            >
              <Form form={form} layout="vertical" initialValues={config ?? undefined}>
                <Row gutter={[16, 0]}>
                  <Col xs={24} md={8}>
                    <Form.Item name="enabled" label="启用闭环" valuePropName="checked">
                      <Switch />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={8}>
                    <Form.Item name="runtime_provider" label="运行时供应商" rules={[{ required: true, message: '请填写供应商' }]}>
                      <Input placeholder="kling / seedance / veo" />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={8}>
                    <Form.Item name="runtime_model" label="运行时模型" rules={[{ required: true, message: '请填写模型' }]}>
                      <Input placeholder="kling-v1" />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={8}>
                    <Form.Item name="reference_mode" label="参考帧策略" rules={[{ required: true, message: '请选择参考帧策略' }]}>
                      <Select options={referenceModeOptions} />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={8}>
                    <Form.Item name="lens" label="Director DSL 默认焦段" rules={[{ required: true, message: '请填写焦段' }]}>
                      <Input placeholder="35mm" />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={8}>
                    <Form.Item name="output_dir" label="输出目录" rules={[{ required: true, message: '请填写输出目录' }]}>
                      <Input placeholder="output/renders" />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={8}>
                    <Form.Item name="qa_threshold" label="QA 阈值">
                      <InputNumber min={0} max={1} step={0.01} className="w-full" />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={8}>
                    <Form.Item name="retry_limit" label="自动重试上限">
                      <InputNumber min={0} max={10} className="w-full" />
                    </Form.Item>
                  </Col>
                  <Col xs={24} md={8}>
                    <Form.Item name="auto_retry" label="启用自动 Retry" valuePropName="checked">
                      <Switch />
                    </Form.Item>
                  </Col>
                </Row>
              </Form>
            </Card>
          ) : null}

          <Card size="small" title="九阶段状态">
            <Table
              rowKey="id"
              size="small"
              columns={stageColumns}
              dataSource={data.stages}
              pagination={false}
              scroll={{ x: 960 }}
            />
          </Card>

          <Card size="small" title="生产闭环 Workflow">
            <Steps
              size="small"
              progressDot
              responsive
              items={data.workflow_stages.map((stage) => ({
                title: stage.title,
                description: stage.evidence || stage.owner,
                status: stage.status === 'done' ? 'finish' : 'wait',
              }))}
            />
          </Card>

          <Card size="small" title="镜头运行计划">
            <Table
              rowKey="shot_id"
              size="small"
              columns={renderColumns}
              dataSource={summary?.render_requests ?? []}
              pagination={false}
              scroll={{ x: 900 }}
            />
          </Card>

          <Row gutter={[16, 16]}>
            <Col xs={24} lg={12}>
              <Card size="small" title="自动 QA">
                <QAReportList reports={summary?.qa.reports ?? []} />
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card size="small" title="自动 Retry">
                <RetryList retries={summary?.retry_requests ?? []} />
              </Card>
            </Col>
          </Row>

          <Collapse
            size="small"
            items={[
              {
                key: 'post',
                label: 'Final Editing / Export',
                children: (
                  <Space direction="vertical" size={4}>
                    <Text>
                      状态：
                      {summary?.post_production.enabled ? (
                        <Tag color="success">Enabled</Tag>
                      ) : (
                        <Tag color="warning">Pending</Tag>
                      )}
                    </Text>
                    <Text type="secondary">输出：{summary?.post_production.output_path ?? '-'}</Text>
                  </Space>
                ),
              },
            ]}
          />
        </>
      ) : (
        <Empty description="暂无 Film Engine 状态" />
      )}
    </div>
  )
}
