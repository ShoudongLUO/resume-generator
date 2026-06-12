/* global Vue */
const ACCENTS = [
  { id: "indigo", hex: "#4f46e5" },
  { id: "teal",   hex: "#0d9488" },
  { id: "slate",  hex: "#334155" },
  { id: "violet", hex: "#7c3aed" },
  { id: "green",  hex: "#15803d" },
  { id: "rose",   hex: "#e11d48" },
  { id: "amber",  hex: "#b45309" },
  { id: "ink",    hex: "#111827" },
];

const RESUME_TEMPLATES = [
  { id: "classic",     name: "经典",   en: "Classic",      layout: "single",       ats: true,  defaultAccent: "ink",    font: "serif" },
  { id: "minimal",     name: "简约",   en: "Minimal",      layout: "single",       ats: true,  defaultAccent: "slate",  font: "sans"  },
  { id: "modern",      name: "现代",   en: "Modern",       layout: "single",       ats: true,  defaultAccent: "indigo", font: "sans"  },
  { id: "professional",name: "商务",   en: "Professional", layout: "single",       ats: true,  defaultAccent: "teal",   font: "sans"  },
  { id: "elegant",     name: "优雅",   en: "Elegant",      layout: "single",       ats: true,  defaultAccent: "ink",    font: "serif" },
  { id: "compact",     name: "紧凑",   en: "Compact",      layout: "single",       ats: true,  defaultAccent: "slate",  font: "sans"  },
  { id: "tech",        name: "科技",   en: "Tech",         layout: "single",       ats: true,  defaultAccent: "indigo", font: "mono"  },
  { id: "timeline",    name: "时间轴", en: "Timeline",     layout: "timeline",     ats: false, defaultAccent: "violet", font: "sans"  },
  { id: "sidebarL",    name: "双栏·左",en: "Sidebar L",    layout: "sidebar-left", ats: false, defaultAccent: "teal",   font: "sans"  },
  { id: "sidebarR",    name: "双栏·右",en: "Sidebar R",    layout: "sidebar-right",ats: false, defaultAccent: "indigo", font: "sans"  },
  { id: "creative",    name: "创意",   en: "Creative",     layout: "sidebar-left", ats: false, defaultAccent: "rose",   font: "sans"  },
  { id: "cards",       name: "卡片",   en: "Cards",        layout: "single",       ats: false, defaultAccent: "green",  font: "sans"  },
];

const ACCENT_HEX = Object.fromEntries(ACCENTS.map(a => [a.id, a.hex]));
function accentHex(id) { return ACCENT_HEX[id] || id || "#4f46e5"; }
function templateById(id) { return RESUME_TEMPLATES.find(t => t.id === id) || RESUME_TEMPLATES[0]; }

const ResumePreview = {
  name: "ResumePreview",
  props: {
    resume: { type: Object, required: true },
    template: { type: Object, required: true },
    accent: { type: String, default: "#4f46e5" },
  },
  computed: {
    b() { return this.resume.basic_info || {}; },
    contacts() {
      const b = this.b;
      return [b.phone, b.email, b.city, ...(b.links || [])].filter(Boolean);
    },
    rootClass() {
      const t = this.template;
      return `resume-page tpl-${t.id} layout-${t.layout} font-${t.font}`;
    },
  },
  methods: {
    span(x) { return [x.start, x.end].filter(Boolean).join(" – "); },
  },
  // Sidebar layouts put name+contact+skills in .r-aside, the rest in .r-main.
  // Single/timeline put everything in one column. The template renders both;
  // CSS hides/positions per layout class.
  template: `
  <div :class="rootClass" :style="{ '--accent': accent }">
    <aside class="r-aside">
      <div class="r-name">{{ b.name }}</div>
      <div class="r-contacts">
        <div v-for="(c,i) in contacts" :key="i" class="r-contact">{{ c }}</div>
      </div>
      <div v-if="(resume.skills||[]).length" class="r-aside-skills">
        <div class="r-aside-h">技能 SKILLS</div>
        <div class="r-skill" v-for="(s,i) in resume.skills" :key="i">{{ s }}</div>
      </div>
    </aside>

    <main class="r-main">
      <header class="r-header">
        <div class="r-name-main">{{ b.name }}</div>
        <div class="r-contacts-main">
          <span v-for="(c,i) in contacts" :key="i" class="r-c">{{ c }}</span>
        </div>
      </header>

      <section v-if="resume.summary" class="r-section r-summary">
        <h2 class="r-h">个人概述</h2>
        <p class="r-p">{{ resume.summary }}</p>
      </section>

      <section v-if="(resume.experiences||[]).length" class="r-section">
        <h2 class="r-h">工作经历</h2>
        <div class="r-entry" v-for="(x,i) in resume.experiences" :key="i">
          <div class="r-entry-top">
            <span class="r-entry-title">{{ x.company }}<template v-if="x.title"> · {{ x.title }}</template></span>
            <span class="r-entry-span">{{ span(x) }}</span>
          </div>
          <ul v-if="(x.bullets||[]).length" class="r-bullets">
            <li v-for="(bl,j) in x.bullets" :key="j">{{ bl }}</li>
          </ul>
          <p v-if="x.description" class="r-p">{{ x.description }}</p>
        </div>
      </section>

      <section v-if="(resume.projects||[]).length" class="r-section">
        <h2 class="r-h">项目经历</h2>
        <div class="r-entry" v-for="(p,i) in resume.projects" :key="i">
          <div class="r-entry-top">
            <span class="r-entry-title">{{ p.name }}<template v-if="p.role"> · {{ p.role }}</template></span>
            <span class="r-entry-span">{{ p.tech_stack }}</span>
          </div>
          <p v-if="p.description" class="r-p">{{ p.description }}</p>
          <p v-if="p.outcome" class="r-p"><b>成果：</b>{{ p.outcome }}</p>
        </div>
      </section>

      <section v-if="(resume.educations||[]).length" class="r-section">
        <h2 class="r-h">教育经历</h2>
        <div class="r-entry" v-for="(e,i) in resume.educations" :key="i">
          <div class="r-entry-top">
            <span class="r-entry-title">{{ e.school }}<template v-if="e.major"> · {{ e.major }}</template><template v-if="e.degree"> · {{ e.degree }}</template></span>
            <span class="r-entry-span">{{ span(e) }}</span>
          </div>
          <p v-if="e.highlights" class="r-p">{{ e.highlights }}</p>
        </div>
      </section>

      <section v-if="(resume.skills||[]).length" class="r-section r-main-skills">
        <h2 class="r-h">技能</h2>
        <p class="r-p">{{ resume.skills.join(' · ') }}</p>
      </section>
    </main>
  </div>
  `,
};
