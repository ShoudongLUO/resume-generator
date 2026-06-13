/* global Vue, RESUME_TEMPLATES, ACCENTS, ResumePreview, accentHex, templateById */
const { createApp, reactive, ref, computed, onMounted } = Vue;

const token = ref(localStorage.getItem("token") || "");
const username = ref(localStorage.getItem("username") || "");

async function api(path, { method = "GET", body, raw = false } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token.value) headers["Authorization"] = "Bearer " + token.value;
  const res = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  if (res.status === 401) { logout(); throw new Error("登录已过期"); }
  if (raw) return res.text();
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "请求失败");
  return data;
}
function logout() {
  token.value = ""; username.value = "";
  localStorage.removeItem("token"); localStorage.removeItem("username");
}

const app = createApp({
  setup() {
    const view = ref("profile");
    const authMode = ref("login");
    const authForm = reactive({ username: "", password: "" });
    const authError = ref("");

    const profile = reactive({ basic_info: { name: "", phone: "", email: "", city: "", links: [] },
      educations: [], experiences: [], projects: [], skills: [], self_summary: "" });
    const skillsText = ref("");

    const llm = reactive({ provider: "gemini", api_key: "", base_url: "", model: "", has_key: false, key_tail: null });
    const models = ref([]);
    const llmMsg = ref("");
    const privacyMode = ref(localStorage.getItem("privacyMode") !== "0");
    function savePrivacy() { localStorage.setItem("privacyMode", privacyMode.value ? "1" : "0"); }

    const intent = reactive({ target_role: "", target_industry: "", target_city: "",
      work_type: "", salary_expect: "", notes: "" });
    const result = ref(null);
    const genError = ref("");
    const genLoading = ref(false);
    const runs = ref([]);

    // templates + accent (persisted)
    const templates = RESUME_TEMPLATES;
    const accents = ACCENTS;
    const templateId = ref(localStorage.getItem("resumeTemplateId") || "modern");
    const accent = ref(localStorage.getItem("resumeAccent") || "");
    const currentTemplate = computed(() => templateById(templateId.value));
    const currentAccent = computed(() => accent.value || accentHex(currentTemplate.value.defaultAccent));
    function pickTemplate(id) { templateId.value = id; localStorage.setItem("resumeTemplateId", id);
      const t = templateById(id); accent.value = accentHex(t.defaultAccent);
      localStorage.setItem("resumeAccent", accent.value); }
    function pickAccent(hex) { accent.value = hex; localStorage.setItem("resumeAccent", hex); }

    // toast
    const toasts = ref([]);
    let toastId = 0;
    function toast(msg, kind = "") {
      const id = ++toastId; toasts.value.push({ id, msg, kind });
      setTimeout(() => { toasts.value = toasts.value.filter(t => t.id !== id); }, 2600);
    }

    const loggedIn = computed(() => !!token.value);

    async function doAuth() {
      authError.value = "";
      try {
        const data = await api(`/api/auth/${authMode.value}`, { method: "POST", body: { ...authForm } });
        token.value = data.token; username.value = data.username;
        localStorage.setItem("token", data.token); localStorage.setItem("username", data.username);
        await loadAll();
      } catch (e) { authError.value = e.message; }
    }

    async function loadProfile() {
      const p = await api("/api/profile");
      Object.assign(profile, p);
      if (!profile.basic_info) profile.basic_info = { name: "", links: [] };
      skillsText.value = (p.skills || []).join(", ");
    }
    async function saveProfile() {
      profile.skills = skillsText.value.split(",").map(s => s.trim()).filter(Boolean);
      await api("/api/profile", { method: "PUT", body: profile });
      toast("主档已保存", "ok");
    }
    const addEdu = () => profile.educations.push({ school: "", major: "", degree: "", start: "", end: "", highlights: "" });
    const addExp = () => profile.experiences.push({ company: "", title: "", start: "", end: "", description: "" });
    const addProj = () => profile.projects.push({ name: "", role: "", tech_stack: "", description: "", outcome: "" });
    const del = (arr, i) => arr.splice(i, 1);

    async function loadLLM() {
      const c = await api("/api/llm-config");
      llm.provider = c.provider || "gemini"; llm.base_url = c.base_url || "";
      llm.model = c.model || ""; llm.has_key = c.has_key; llm.key_tail = c.key_tail;
    }
    async function fetchModels() {
      llmMsg.value = "拉取中…";
      try {
        const r = await api("/api/llm-config/models", { method: "POST",
          body: { provider: llm.provider, api_key: llm.api_key || null, base_url: llm.base_url || null } });
        models.value = r.models; llmMsg.value = `获取到 ${r.models.length} 个模型`;
      } catch (e) { llmMsg.value = e.message; }
    }
    async function saveLLM() {
      try {
        await api("/api/llm-config", { method: "PUT", body: { provider: llm.provider,
          api_key: llm.api_key || null, base_url: llm.base_url || null, model: llm.model || null } });
        llm.api_key = ""; await loadLLM(); toast("AI 设置已保存", "ok");
      } catch (e) { llmMsg.value = e.message; toast(e.message, "err"); }
    }

    const ERR_MSG = {
      PROFILE_EMPTY: "请先在「简历主档」填写姓名和至少一段经历",
      LLM_NOT_CONFIGURED: "请先在「AI 设置」配置 API key 并选择模型",
      QUOTA_EXCEEDED: "今日生成次数已用尽，请明日再试",
      LLM_UNAVAILABLE: "AI 服务暂时不可用（超时/网络），请稍后重试",
      PARSE_FAILED: "AI 返回解析失败，请重试",
      TARGET_ROLE_REQUIRED: "请填写目标岗位",
    };
    async function generate() {
      genError.value = ""; result.value = null; genLoading.value = true;
      try {
        const r = await api("/api/generate", { method: "POST", body: { ...intent, privacy_mode: privacyMode.value } });
        if (r.error) { genError.value = ERR_MSG[r.error] || r.error; }
        else { result.value = r; await loadRuns(); }
      } catch (e) { genError.value = e.message; }
      finally { genLoading.value = false; }
    }

    async function loadRuns() { runs.value = await api("/api/runs"); }
    async function openRun(id) {
      const r = await api(`/api/runs/${id}`); result.value = r; view.value = "generate";
      Object.assign(intent, { target_role: r.target_role, target_industry: r.target_industry || "",
        target_city: r.target_city || "", work_type: r.work_type || "",
        salary_expect: r.salary_expect || "", notes: r.notes || "" });
    }

    async function copyMarkdown() {
      const md = await api(`/api/runs/${result.value.run_id}/markdown`, { raw: true });
      await navigator.clipboard.writeText(md); toast("Markdown 已复制", "ok");
    }
    async function downloadMarkdown() {
      const md = await api(`/api/runs/${result.value.run_id}/markdown`, { raw: true });
      const blob = new Blob([md], { type: "text/markdown" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = "resume.md"; a.click();
    }
    const printResume = () => window.print();

    async function loadAll() { await Promise.all([loadProfile(), loadLLM(), loadRuns()]); }
    onMounted(() => { if (loggedIn.value) loadAll(); });

    return { view, authMode, authForm, authError, doAuth, loggedIn, username, logout,
      profile, skillsText, saveProfile, addEdu, addExp, addProj, del,
      llm, models, llmMsg, fetchModels, saveLLM,
      intent, result, genError, genLoading, generate,
      runs, openRun, copyMarkdown, downloadMarkdown, printResume,
      templates, accents, templateId, currentTemplate, currentAccent, pickTemplate, pickAccent,
      toasts, accentHex, privacyMode, savePrivacy };
  },
  template: `
  <div v-if="!loggedIn" class="auth-wrap">
    <div class="card auth-card">
      <h2>{{ authMode === 'login' ? '欢迎回来' : '创建账号' }}</h2>
      <p class="muted">简历生成与公司推荐</p>
      <label>用户名</label><input v-model="authForm.username" @keyup.enter="doAuth" />
      <label>密码</label><input type="password" v-model="authForm.password" @keyup.enter="doAuth" />
      <p class="error" v-if="authError">{{ authError }}</p>
      <p style="margin-top:14px;"><button class="primary" style="width:100%" @click="doAuth">{{ authMode === 'login' ? '登录' : '注册' }}</button></p>
      <p class="muted" @click="authMode = authMode==='login'?'register':'login'" style="cursor:pointer;text-align:center;">
        {{ authMode === 'login' ? '没有账号？去注册' : '已有账号？去登录' }}</p>
    </div>
  </div>

  <div v-else>
    <div class="topbar">
      <div class="brand"><span class="logo"></span> 简历生成器</div>
      <nav>
        <button :class="{active:view==='profile'}" @click="view='profile'">简历主档</button>
        <button :class="{active:view==='settings'}" @click="view='settings'">AI 设置</button>
        <button :class="{active:view==='generate'}" @click="view='generate'">生成</button>
        <button :class="{active:view==='history'}" @click="view='history'">历史</button>
      </nav>
      <span class="spacer"></span>
      <span class="muted">{{ username }}</span>
      <button class="ghost" @click="logout">退出</button>
    </div>

    <div class="container">
      <!-- profile -->
      <div v-show="view==='profile'">
        <h1 class="page-title">简历主档</h1>
        <p class="page-sub">填写一次，后续按不同求职意向反复生成定制简历。</p>
        <div class="card">
          <h3>基本信息</h3>
          <div class="row">
            <div><label>姓名</label><input v-model="profile.basic_info.name" /></div>
            <div><label>电话</label><input v-model="profile.basic_info.phone" /></div>
            <div><label>邮箱</label><input v-model="profile.basic_info.email" /></div>
            <div><label>城市</label><input v-model="profile.basic_info.city" /></div>
          </div>
        </div>
        <div class="card">
          <h3>教育经历 <button class="ghost" @click="addEdu">+ 添加</button></h3>
          <div class="item" v-for="(e,i) in profile.educations" :key="'e'+i">
            <div class="row">
              <div><label>学校</label><input v-model="e.school" /></div>
              <div><label>专业</label><input v-model="e.major" /></div>
              <div><label>学历</label><input v-model="e.degree" /></div>
              <div><label>起</label><input v-model="e.start" /></div>
              <div><label>止</label><input v-model="e.end" /></div>
            </div>
            <button class="ghost item-del" @click="del(profile.educations,i)">删除</button>
          </div>
          <p class="muted" v-if="!profile.educations.length">还没有教育经历</p>
        </div>
        <div class="card">
          <h3>工作经历 <button class="ghost" @click="addExp">+ 添加</button></h3>
          <div class="item" v-for="(x,i) in profile.experiences" :key="'x'+i">
            <div class="row">
              <div><label>公司</label><input v-model="x.company" /></div>
              <div><label>职位</label><input v-model="x.title" /></div>
              <div><label>起</label><input v-model="x.start" /></div>
              <div><label>止</label><input v-model="x.end" /></div>
            </div>
            <label>职责与业绩</label><textarea rows="3" v-model="x.description"></textarea>
            <button class="ghost item-del" @click="del(profile.experiences,i)">删除</button>
          </div>
          <p class="muted" v-if="!profile.experiences.length">还没有工作经历</p>
        </div>
        <div class="card">
          <h3>项目经历 <button class="ghost" @click="addProj">+ 添加</button></h3>
          <div class="item" v-for="(p,i) in profile.projects" :key="'p'+i">
            <div class="row">
              <div><label>项目名</label><input v-model="p.name" /></div>
              <div><label>角色</label><input v-model="p.role" /></div>
              <div><label>技术栈</label><input v-model="p.tech_stack" /></div>
            </div>
            <label>描述</label><textarea rows="2" v-model="p.description"></textarea>
            <label>成果</label><input v-model="p.outcome" />
            <button class="ghost item-del" @click="del(profile.projects,i)">删除</button>
          </div>
          <p class="muted" v-if="!profile.projects.length">还没有项目经历</p>
        </div>
        <div class="card">
          <h3>技能与自评</h3>
          <label>技能（逗号分隔）</label><input v-model="skillsText" />
          <label>自我评价</label><textarea rows="3" v-model="profile.self_summary"></textarea>
        </div>
        <button class="primary" @click="saveProfile">保存主档</button>
      </div>

      <!-- settings -->
      <div v-show="view==='settings'">
        <h1 class="page-title">AI 设置</h1>
        <p class="page-sub">使用你自己的 API key，数据加密存储。</p>
        <div class="card">
          <h3>模型配置</h3>
          <label>Provider</label>
          <select v-model="llm.provider">
            <option value="gemini">Google Gemini</option>
            <option value="openai_compat">OpenAI 兼容</option>
          </select>
          <div v-if="llm.provider==='openai_compat'">
            <label>服务地址 (base_url)</label><input v-model="llm.base_url" placeholder="https://api.example.com/v1" />
          </div>
          <label>API Key <span class="muted" v-if="llm.has_key">（已保存 ****{{ llm.key_tail }}，留空则不修改）</span></label>
          <input type="password" v-model="llm.api_key" placeholder="粘贴你的 API key" />
          <p style="margin-top:10px;"><button class="ghost" @click="fetchModels">拉取模型</button></p>
          <div v-if="models.length">
            <label>选择模型</label>
            <select v-model="llm.model"><option v-for="m in models" :key="m" :value="m">{{ m }}</option></select>
          </div>
          <p class="muted">{{ llmMsg }}</p>
          <button class="primary" @click="saveLLM">保存设置</button>
        </div>
        <div class="card">
          <h3>隐私</h3>
          <label style="display:flex;align-items:flex-start;gap:10px;cursor:pointer;font-size:14px;color:var(--text);">
            <input type="checkbox" v-model="privacyMode" @change="savePrivacy" style="width:auto;margin-top:2px;" />
            <span>隐私模式（推荐开启）：发送给 AI 前自动隐去<b>姓名 / 邮箱 / 电话 / 链接</b>，并把<b>公司名</b>替换为占位符，返回后在本地还原。学校、项目、技能、城市照常发送。</span>
          </label>
          <p class="muted" style="margin-top:8px;">{{ privacyMode ? '已开启：第三方大模型不会看到你的联系方式与公司名。' : '已关闭：将按原文发送给大模型。' }}</p>
        </div>
      </div>

      <!-- generate -->
      <div v-show="view==='generate'">
        <h1 class="page-title no-print">生成简历</h1>
        <div class="card no-print">
          <h3>求职意向</h3>
          <div class="row">
            <div><label>目标岗位 *</label><input v-model="intent.target_role" /></div>
            <div><label>目标行业</label><input v-model="intent.target_industry" /></div>
            <div><label>目标城市</label><input v-model="intent.target_city" /></div>
            <div><label>工作类型</label><input v-model="intent.work_type" placeholder="全职/实习/远程" /></div>
            <div><label>薪资期望</label><input v-model="intent.salary_expect" /></div>
          </div>
          <label>补充说明</label><textarea rows="2" v-model="intent.notes"></textarea>
          <p style="margin-top:10px;"><button class="primary" @click="generate" :disabled="genLoading">
            {{ genLoading ? '生成中…' : '生成简历与推荐' }}</button></p>
          <p class="error" v-if="genError">{{ genError }}</p>
        </div>

        <div v-if="result">
          <!-- template picker -->
          <div class="card no-print">
            <h3>模板与配色
              <span class="badge" :class="currentTemplate.ats ? 'ats' : 'noats'">
                {{ currentTemplate.ats ? 'ATS 友好' : '机器筛选解析略弱' }}</span>
            </h3>
            <div class="tpl-bar">
              <div v-for="t in templates" :key="t.id" class="tpl-chip" :class="{active: t.id===templateId}" @click="pickTemplate(t.id)">
                <div class="tpl-thumb" :class="['thumb-'+t.layout, {'thumb-pro': t.id==='professional'}]" :style="{'--accent': accentHex(t.defaultAccent)}">
                  <div class="th-strip"></div>
                  <div class="th-body">
                    <div class="th-head"></div>
                    <div class="th-line"></div>
                    <div class="th-line short"></div>
                    <div class="th-line"></div>
                    <div class="th-line short"></div>
                  </div>
                </div>
                <div class="tpl-name">{{ t.name }}</div>
              </div>
            </div>
            <div class="accent-dots">
              <span v-for="a in accents" :key="a.id" class="accent-dot"
                :class="{active: currentAccent===a.hex}" :style="{background:a.hex}" @click="pickAccent(a.hex)"></span>
            </div>
          </div>

          <div class="results">
            <div>
              <div class="actions no-print">
                <button class="ghost" @click="copyMarkdown">复制 Markdown</button>
                <button class="ghost" @click="downloadMarkdown">下载 .md</button>
                <button class="primary" @click="printResume">打印 / 存为 PDF</button>
              </div>
              <resume-preview :resume="result.tailored_resume" :template="currentTemplate" :accent="currentAccent"></resume-preview>
            </div>

            <div class="card rec-col">
              <h3>推荐投递公司</h3>
              <p class="muted">AI 基于你的经历推断，非实时招聘数据</p>
              <div class="item" v-for="(r,i) in result.recommendations" :key="i">
                <strong>{{ r.company }}</strong> <span class="muted">{{ r.type }}</span>
                <p class="muted" style="margin:4px 0;">建议岗位：{{ r.suggested_role }}</p>
                <p style="margin:4px 0;font-size:13px;">{{ r.reason }}</p>
              </div>
            </div>

            <div class="card gap-col">
              <h3>需要完善的点</h3>
              <div class="item" :class="'gap-'+(g.importance||'低')" v-for="(g,i) in result.gaps" :key="i">
                <strong>{{ g.gap }}</strong> <span class="badge">{{ g.importance }}</span>
                <p style="margin:4px 0;font-size:13px;">{{ g.suggestion }}</p>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="empty no-print">填写求职意向后点「生成」，结果会显示在这里。</div>
      </div>

      <!-- history -->
      <div v-show="view==='history'">
        <h1 class="page-title">生成历史</h1>
        <div class="card">
          <div class="item" v-for="r in runs" :key="r.id" @click="openRun(r.id)" style="cursor:pointer;">
            <strong>{{ r.target_role }}</strong>
            <span class="muted">　{{ r.target_city }} · {{ r.created_at?.slice(0,10) }} · {{ r.model_used }}</span>
          </div>
          <p class="empty" v-if="!runs.length">暂无记录</p>
        </div>
      </div>
    </div>

    <div class="toast-wrap">
      <div v-for="t in toasts" :key="t.id" class="toast" :class="t.kind">{{ t.msg }}</div>
    </div>
  </div>
  `,
});
app.component("ResumePreview", ResumePreview);
app.mount("#app");
