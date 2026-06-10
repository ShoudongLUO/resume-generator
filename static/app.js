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

createApp({
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

    const intent = reactive({ target_role: "", target_industry: "", target_city: "",
      work_type: "", salary_expect: "", notes: "" });
    const result = ref(null);
    const genError = ref("");
    const genLoading = ref(false);

    const runs = ref([]);

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
      alert("已保存");
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
        llm.api_key = ""; llmMsg.value = "已保存"; await loadLLM();
      } catch (e) { llmMsg.value = e.message; }
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
        const r = await api("/api/generate", { method: "POST", body: { ...intent } });
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
      await navigator.clipboard.writeText(md); alert("Markdown 已复制");
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
      runs, openRun, copyMarkdown, downloadMarkdown, printResume };
  },
  template: `
  <div v-if="!loggedIn" class="container">
    <div class="card" style="max-width:380px;margin:80px auto;">
      <h2>{{ authMode === 'login' ? '登录' : '注册' }}</h2>
      <label>用户名</label><input v-model="authForm.username" />
      <label>密码</label><input type="password" v-model="authForm.password" />
      <p class="error" v-if="authError">{{ authError }}</p>
      <p><button class="primary" @click="doAuth">{{ authMode === 'login' ? '登录' : '注册' }}</button></p>
      <p class="muted" @click="authMode = authMode==='login'?'register':'login'" style="cursor:pointer;">
        {{ authMode === 'login' ? '没有账号？去注册' : '已有账号？去登录' }}</p>
    </div>
  </div>

  <div v-else>
    <div class="topbar">
      <strong>简历生成器</strong>
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
      <div v-show="view==='profile'">
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
            <button class="ghost" @click="del(profile.educations,i)">删除</button>
          </div>
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
            <button class="ghost" @click="del(profile.experiences,i)">删除</button>
          </div>
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
            <button class="ghost" @click="del(profile.projects,i)">删除</button>
          </div>
        </div>
        <div class="card">
          <h3>技能与自评</h3>
          <label>技能（逗号分隔）</label><input v-model="skillsText" />
          <label>自我评价</label><textarea rows="3" v-model="profile.self_summary"></textarea>
        </div>
        <button class="primary" @click="saveProfile">保存主档</button>
      </div>

      <div v-show="view==='settings'">
        <div class="card">
          <h3>AI 模型设置</h3>
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
          <p>
            <button class="ghost" @click="fetchModels">拉取模型</button>
          </p>
          <div v-if="models.length">
            <label>选择模型</label>
            <select v-model="llm.model">
              <option v-for="m in models" :key="m" :value="m">{{ m }}</option>
            </select>
          </div>
          <p class="muted">{{ llmMsg }}</p>
          <button class="primary" @click="saveLLM">保存设置</button>
        </div>
      </div>

      <div v-show="view==='generate'">
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
          <p>
            <button class="primary" @click="generate" :disabled="genLoading">
              {{ genLoading ? '生成中…' : '生成简历与推荐' }}</button>
          </p>
          <p class="error" v-if="genError">{{ genError }}</p>
        </div>

        <div v-if="result" class="results">
          <div class="card">
            <div class="actions no-print">
              <button class="ghost" @click="copyMarkdown">复制 Markdown</button>
              <button class="ghost" @click="downloadMarkdown">下载 .md</button>
              <button class="ghost" @click="printResume">打印 / 存为 PDF</button>
            </div>
            <h2>{{ result.tailored_resume.basic_info?.name }}</h2>
            <p class="muted">{{ [result.tailored_resume.basic_info?.phone,
              result.tailored_resume.basic_info?.email,
              result.tailored_resume.basic_info?.city].filter(Boolean).join(' | ') }}</p>
            <p v-if="result.tailored_resume.summary"><strong>概述：</strong>{{ result.tailored_resume.summary }}</p>
            <div v-if="result.tailored_resume.experiences?.length">
              <h3>工作经历</h3>
              <div class="item" v-for="(x,i) in result.tailored_resume.experiences" :key="i">
                <strong>{{ x.company }} · {{ x.title }}</strong> <span class="muted">{{ x.start }}–{{ x.end }}</span>
                <ul><li v-for="(b,j) in (x.bullets||[])" :key="j">{{ b }}</li></ul>
              </div>
            </div>
            <div v-if="result.tailored_resume.projects?.length">
              <h3>项目经历</h3>
              <div class="item" v-for="(p,i) in result.tailored_resume.projects" :key="i">
                <strong>{{ p.name }}</strong> <span class="muted">{{ p.role }}</span>
                <p>{{ p.description }}</p><p v-if="p.outcome">成果：{{ p.outcome }}</p>
              </div>
            </div>
            <div v-if="result.tailored_resume.educations?.length">
              <h3>教育经历</h3>
              <div class="item" v-for="(e,i) in result.tailored_resume.educations" :key="i">
                {{ e.school }} · {{ e.major }} · {{ e.degree }} <span class="muted">{{ e.start }}–{{ e.end }}</span>
              </div>
            </div>
            <div v-if="result.tailored_resume.skills?.length">
              <h3>技能</h3><p>{{ result.tailored_resume.skills.join(' · ') }}</p>
            </div>
          </div>

          <div class="card rec-col">
            <h3>推荐投递公司</h3>
            <p class="muted">AI 基于你的经历推断，非实时招聘数据</p>
            <div class="item" v-for="(r,i) in result.recommendations" :key="i">
              <strong>{{ r.company }}</strong> <span class="muted">{{ r.type }}</span>
              <p>建议岗位：{{ r.suggested_role }}</p>
              <p>{{ r.reason }}</p>
            </div>
          </div>

          <div class="card gap-col">
            <h3>需要完善的点</h3>
            <div class="item" :class="'gap-'+(g.importance||'低')" v-for="(g,i) in result.gaps" :key="i">
              <strong>{{ g.gap }}</strong> <span class="muted">[{{ g.importance }}]</span>
              <p>{{ g.suggestion }}</p>
            </div>
          </div>
        </div>
      </div>

      <div v-show="view==='history'">
        <div class="card">
          <h3>生成历史</h3>
          <div class="item" v-for="r in runs" :key="r.id" @click="openRun(r.id)" style="cursor:pointer;">
            <strong>{{ r.target_role }}</strong>
            <span class="muted">{{ r.target_city }} · {{ r.created_at?.slice(0,10) }} · {{ r.model_used }}</span>
          </div>
          <p class="muted" v-if="!runs.length">暂无记录</p>
        </div>
      </div>
    </div>
  </div>
  `,
}).mount("#app");
