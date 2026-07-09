const PROGRESS_OPTIONS = [20, 50, 70, 90, 100];
const BAR_COLORS = ["#2f6fed", "#0f8b63", "#b7791f", "#c2410c", "#7c3aed", "#0891b2", "#be185d", "#4d7c0f"];

let state = {
  users: [],
  projects: [],
  tasks: [],
  stats: {},
  selectedProjectId: null,
  adminPassword: localStorage.getItem("adminPassword") || "",
};

const $ = (id) => document.getElementById(id);
const pct = (value) => `${Number(value || 0).toFixed(1).replace(".0", "")}%`;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function toast(message) {
  const node = $("toast");
  node.textContent = message;
  node.classList.add("show");
  setTimeout(() => node.classList.remove("show"), 2200);
}

async function api(path, options = {}) {
  const headers = {"Content-Type": "application/json", ...(options.headers || {})};
  if (state.adminPassword) headers["X-Admin-Password"] = state.adminPassword;
  const res = await fetch(path, {...options, headers});
  if (!res.ok) {
    let message = "请求失败";
    try {
      message = (await res.json()).error || message;
    } catch (_) {}
    throw new Error(message);
  }
  return res.json();
}

async function loadAll() {
  const [bootstrap, stats] = await Promise.all([api("/api/bootstrap"), api("/api/stats")]);
  const activeProject = bootstrap.projects.find((item) => item.active !== 0);
  state = {
    ...state,
    ...bootstrap,
    stats,
    selectedProjectId: state.selectedProjectId || activeProject?.id || null,
  };
  renderAll();
}

function optionList(values, selected) {
  return values.map((value) => `<option value="${value}" ${String(value) === String(selected) ? "selected" : ""}>${value}%</option>`).join("");
}

function renderSelect(select, records, label = "name") {
  select.innerHTML = records
    .filter((item) => item.active !== 0)
    .map((item) => `<option value="${item.id}">${escapeHtml(item[label])}</option>`)
    .join("");
}

function table(node, headers, records, rowFn) {
  if (!records || records.length === 0) {
    node.innerHTML = `<tr><td>暂无数据</td></tr>`;
    return;
  }
  node.innerHTML = `
    <thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead>
    <tbody>${records.map(rowFn).join("")}</tbody>
  `;
}

function currentUserId() {
  return Number($("currentUser").value);
}

function projectById(projectId) {
  return state.projects.find((item) => Number(item.id) === Number(projectId));
}

function activeProjectTasks(projectId) {
  return state.tasks.filter((task) => task.active !== 0 && Number(task.project_id) === Number(projectId));
}

function projectStat(projectId) {
  return (state.stats.project_progress || []).find((item) => Number(item.id) === Number(projectId));
}

function renderProgressOverview(targetId) {
  const target = $(targetId);
  const rows = state.stats.project_progress || [];
  if (!rows.length) {
    target.innerHTML = `<div class="empty">暂无项目</div>`;
    return;
  }
  target.innerHTML = rows.map((row) => `
    <div class="progress-item">
      <div class="progress-head">
        <strong>${escapeHtml(row.name)}</strong>
        <span>${pct(row.progress)}</span>
      </div>
      <div class="progress-track">
        <div class="progress-fill" style="width:${Math.min(100, Number(row.progress || 0))}%"></div>
      </div>
      <div class="progress-meta">已确认工作量 ${Number(row.done_workload || 0).toFixed(2)} / 总工作量 ${Number(row.total_workload || 0).toFixed(2)}</div>
    </div>
  `).join("");
}

function renderUserView() {
  renderSelect($("currentUser"), state.users);
  renderSelect($("projectSelect"), state.projects);
  $("projectProgress").innerHTML = optionList(PROGRESS_OPTIONS, 20);
  $("researchProgress").innerHTML = optionList(PROGRESS_OPTIONS, 20);
  updateTaskSelect();
  renderMyHistory();
}

function renderResearchOverview() {
  table($("userResearchOverview"), ["姓名", "大论文标题", "阶段", "进度", "更新时间"], state.stats.research_latest || [], (row) => `
    <tr>
      <td>${escapeHtml(row.user_name)}</td>
      <td>${escapeHtml(row.title)}</td>
      <td>${escapeHtml(row.stage)}</td>
      <td>${pct(row.progress)}</td>
      <td>${row.created_at}</td>
    </tr>
  `);
}

function updateTaskSelect() {
  renderSelect($("taskSelect"), activeProjectTasks($("projectSelect").value));
}

function renderMyHistory() {
  const user = state.users.find((item) => item.id === currentUserId());
  if (!user) return;
  const projectRows = (state.stats.project_history || []).filter((row) => row.user_name === user.name);
  const researchRows = (state.stats.research_history || []).filter((row) => row.user_name === user.name);
  table($("myProjectHistory"), ["时间", "项目", "任务", "进度", "贡献工作量", "细节汇报"], projectRows, (row) => `
    <tr>
      <td>${row.created_at}</td>
      <td>${escapeHtml(row.project_name)}</td>
      <td>${escapeHtml(row.task_name)}</td>
      <td>${pct(row.progress)}</td>
      <td>${row.contribution_workload}</td>
      <td>${escapeHtml(row.note)}</td>
    </tr>
  `);
  table($("myResearchHistory"), ["时间", "标题", "阶段", "进度", "细节汇报"], researchRows, (row) => `
    <tr><td>${row.created_at}</td><td>${escapeHtml(row.title)}</td><td>${escapeHtml(row.stage)}</td><td>${pct(row.progress)}</td><td>${escapeHtml(row.note)}</td></tr>
  `);
}

function renderAdminView() {
  $("adminPassword").value = state.adminPassword;
  $("exportExcel").disabled = !state.adminPassword;
  renderSelect($("newTaskProject"), state.projects);
  renderProgressOverview("adminProjectOverview");
  renderProjectFolders();
  renderProjectDetail();
  renderResearchStats();
  renderUsers();
  renderProjects();
}

function renderProjectFolders() {
  const rows = state.projects.filter((project) => project.active !== 0);
  $("projectFolders").innerHTML = rows.map((project) => {
    const stat = projectStat(project.id) || {};
    const active = Number(project.id) === Number(state.selectedProjectId) ? " active" : "";
    return `
      <button class="folder${active}" data-open-project="${project.id}">
        <span class="folder-icon">▣</span>
        <span>${escapeHtml(project.name)}</span>
        <small>${pct(stat.progress)}</small>
      </button>
    `;
  }).join("");
}

function renderProjectDetail() {
  const project = projectById(state.selectedProjectId);
  if (!project) {
    $("projectDetail").innerHTML = `<div class="empty">请选择项目</div>`;
    return;
  }

  const contributions = (state.stats.contributions || []).filter((row) => Number(row.project_id) === Number(project.id));
  const tasks = (state.stats.task_rollup || []).filter((row) => Number(row.project_id) === Number(project.id));
  const latestSubmissions = (state.stats.project_latest_submissions || []).filter((row) => Number(row.project_id) === Number(project.id));
  const history = (state.stats.project_history || []).filter((row) => Number(row.project_id) === Number(project.id));
  const confirmations = (state.stats.confirmations || []).filter((row) => Number(row.project_id) === Number(project.id));
  const stat = projectStat(project.id) || {};

  $("projectDetail").innerHTML = `
    <div class="detail-head">
      <div>
        <h3>${escapeHtml(project.name)}</h3>
        <p>项目确认进度 ${pct(stat.progress)}，总工作量 ${Number(stat.total_workload || 0).toFixed(2)}</p>
      </div>
      <span class="badge">${project.active ? "启用" : "停用"}</span>
    </div>

    <div class="visual-block">
      <h3>人员贡献占比</h3>
      ${renderContributionBar(contributions)}
    </div>

    <div class="visual-block">
      <h3>子任务工作量与完成度</h3>
      ${renderTaskBar(tasks)}
    </div>

    <div class="grid two">
      <section>
        <h3>个人项目贡献明细</h3>
        <div class="table-wrap"><table id="projectContributionDetail"></table></div>
      </section>
      <section>
        <h3>任务修改与确认</h3>
        <div class="table-wrap"><table id="projectTaskEdit"></table></div>
      </section>
    </div>

    <div class="grid two">
      <section>
        <h3>项目推进历史</h3>
        <div class="table-wrap"><table id="projectHistoryDetail"></table></div>
      </section>
      <section>
        <h3>确认修正历史</h3>
        <div class="table-wrap"><table id="projectConfirmHistory"></table></div>
      </section>
    </div>
  `;

  table($("projectContributionDetail"), ["姓名", "任务", "最新填报进度", "工作量", "贡献工作量", "时间", "细节汇报"], latestSubmissions, (row) => `
    <tr>
      <td>${escapeHtml(row.user_name)}</td>
      <td>${escapeHtml(row.task_name)}</td>
      <td>${pct(row.progress)}</td>
      <td>${row.workload}</td>
      <td>${row.contribution_workload}</td>
      <td>${row.created_at}</td>
      <td>${escapeHtml(row.note)}</td>
    </tr>
  `);

  table($("projectTaskEdit"), ["任务", "工作量", "状态", "累计填报", "确认进度", "操作"], tasks, (row) => `
    <tr>
      <td><input value="${escapeHtml(row.task_name)}" data-task-name="${row.id}"></td>
      <td><input type="number" min="0" step="0.1" value="${row.workload}" data-task-workload="${row.id}"></td>
      <td>
        <select data-task-active="${row.id}">
          <option value="1" ${row.active ? "selected" : ""}>启用</option>
          <option value="0" ${!row.active ? "selected" : ""}>停用</option>
        </select>
      </td>
      <td>${pct(row.submitted_progress)}</td>
      <td><input type="number" min="0" max="100" step="1" value="${row.confirmed_progress}" data-confirm="${row.id}"></td>
      <td class="actions">
        <button data-save-task="${row.id}">保存</button>
        <button data-confirm-task="${row.id}">确认</button>
      </td>
    </tr>
  `);

  table($("projectHistoryDetail"), ["时间", "姓名", "任务", "进度", "细节汇报"], history, (row) => `
    <tr>
      <td>${row.created_at}</td>
      <td>${escapeHtml(row.user_name)}</td>
      <td>${escapeHtml(row.task_name)}</td>
      <td>${pct(row.progress)}</td>
      <td>${escapeHtml(row.note)}</td>
    </tr>
  `);

  table($("projectConfirmHistory"), ["时间", "任务", "确认进度", "细节汇报"], confirmations, (row) => `
    <tr>
      <td>${row.created_at}</td>
      <td>${escapeHtml(row.task_name)}</td>
      <td>${pct(row.confirmed_progress)}</td>
      <td>${escapeHtml(row.admin_note)}</td>
    </tr>
  `);
}

function renderContributionBar(contributions) {
  if (!contributions.length) return `<div class="empty">暂无个人贡献数据</div>`;
  const total = contributions.reduce((sum, row) => sum + Number(row.contribution_workload || 0), 0);
  const segments = contributions.map((row, index) => {
    const share = total > 0 ? Number(row.contribution_workload || 0) * 100 / total : 0;
    return `
      <div class="stack-segment" style="width:${Math.max(share, 3)}%; background:${BAR_COLORS[index % BAR_COLORS.length]}" title="${escapeHtml(row.user_name)} ${pct(share)}">
        ${escapeHtml(row.user_name)} ${pct(share)}
      </div>
    `;
  }).join("");
  const legend = contributions.map((row, index) => {
    const share = total > 0 ? Number(row.contribution_workload || 0) * 100 / total : 0;
    return `<span><i style="background:${BAR_COLORS[index % BAR_COLORS.length]}"></i>${escapeHtml(row.user_name)}：${pct(share)}，折算项目 ${pct(row.contribution_percent)}</span>`;
  }).join("");
  return `<div class="stack-bar">${segments}</div><div class="legend">${legend}</div>`;
}

function renderTaskBar(tasks) {
  const activeTasks = tasks.filter((task) => task.active !== 0);
  if (!activeTasks.length) return `<div class="empty">暂无任务</div>`;
  const total = activeTasks.reduce((sum, row) => sum + Number(row.workload || 0), 0);
  const segments = activeTasks.map((task, index) => {
    const share = total > 0 ? Number(task.workload || 0) * 100 / total : 0;
    return `
      <div class="task-segment" style="width:${Math.max(share, 8)}%">
        <div class="task-fill" style="height:${Math.min(100, Number(task.confirmed_progress || 0))}%; background:${BAR_COLORS[index % BAR_COLORS.length]}"></div>
        <span>${escapeHtml(task.task_name)}</span>
        <small>占${pct(share)} / 完成${pct(task.confirmed_progress)}</small>
      </div>
    `;
  }).join("");
  return `<div class="task-bar">${segments}</div>`;
}

function renderResearchStats() {
  table($("researchStats"), ["姓名", "大论文标题", "阶段", "进度", "细节汇报", "更新时间"], state.stats.research_latest || [], (row) => `
    <tr>
      <td>${escapeHtml(row.user_name)}</td>
      <td>${escapeHtml(row.title)}</td>
      <td>${escapeHtml(row.stage)}</td>
      <td>${pct(row.progress)}</td>
      <td>${escapeHtml(row.note)}</td>
      <td>${row.created_at}</td>
    </tr>
  `);
}

function renderUsers() {
  $("userList").innerHTML = state.users.map((user) => `
    <div class="list-row">
      <input value="${escapeHtml(user.name)}" data-user-name="${user.id}">
      <select data-user-active="${user.id}">
        <option value="1" ${user.active ? "selected" : ""}>启用</option>
        <option value="0" ${!user.active ? "selected" : ""}>停用</option>
      </select>
      <button data-save-user="${user.id}">保存</button>
    </div>
  `).join("");
}

function renderProjects() {
  $("projectList").innerHTML = state.projects.map((project) => `
    <div class="list-row">
      <input value="${escapeHtml(project.name)}" data-project-name="${project.id}">
      <select data-project-active="${project.id}">
        <option value="1" ${project.active ? "selected" : ""}>启用</option>
        <option value="0" ${!project.active ? "selected" : ""}>停用</option>
      </select>
      <button data-save-project="${project.id}">保存</button>
    </div>
  `).join("");
}

function renderAll() {
  renderUserView();
  renderAdminView();
}

document.addEventListener("click", async (event) => {
  try {
    const tab = event.target.closest(".tab");
    if (tab) {
      document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".view").forEach((item) => item.classList.remove("active"));
      tab.classList.add("active");
      $(tab.dataset.view).classList.add("active");
    }

    const openProject = event.target.closest("[data-open-project]")?.dataset.openProject;
    if (openProject) {
      state.selectedProjectId = Number(openProject);
      renderProjectFolders();
      renderProjectDetail();
    }

    const saveUser = event.target.dataset.saveUser;
    if (saveUser) {
      await api(`/api/admin/users/${saveUser}`, {
        method: "PUT",
        body: JSON.stringify({
          name: document.querySelector(`[data-user-name="${saveUser}"]`).value,
          active: document.querySelector(`[data-user-active="${saveUser}"]`).value,
        }),
      });
      toast("人员已保存");
      await loadAll();
    }

    const saveProject = event.target.dataset.saveProject;
    if (saveProject) {
      await api(`/api/admin/projects/${saveProject}`, {
        method: "PUT",
        body: JSON.stringify({
          name: document.querySelector(`[data-project-name="${saveProject}"]`).value,
          active: document.querySelector(`[data-project-active="${saveProject}"]`).value,
        }),
      });
      toast("项目已保存");
      await loadAll();
    }

    const confirmTask = event.target.dataset.confirmTask;
    if (confirmTask) {
      await api("/api/admin/confirm-task", {
        method: "POST",
        body: JSON.stringify({
          task_id: confirmTask,
          confirmed_progress: document.querySelector(`[data-confirm="${confirmTask}"]`).value,
        }),
      });
      toast("任务进度已确认");
      await loadAll();
    }

    const saveTask = event.target.dataset.saveTask;
    if (saveTask) {
      await api(`/api/admin/tasks/${saveTask}`, {
        method: "PUT",
        body: JSON.stringify({
          name: document.querySelector(`[data-task-name="${saveTask}"]`).value,
          workload: document.querySelector(`[data-task-workload="${saveTask}"]`).value,
          active: document.querySelector(`[data-task-active="${saveTask}"]`).value,
          confirmed_progress: document.querySelector(`[data-confirm="${saveTask}"]`).value,
        }),
      });
      toast("任务已保存");
      await loadAll();
    }
  } catch (err) {
    toast(err.message);
  }
});

$("projectSelect").addEventListener("change", updateTaskSelect);
$("currentUser").addEventListener("change", renderMyHistory);

$("projectForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/api/project-submissions", {
      method: "POST",
      body: JSON.stringify({
        user_id: currentUserId(),
        project_id: Number($("projectSelect").value),
        task_id: Number($("taskSelect").value),
        progress: Number($("projectProgress").value),
        note: $("projectNote").value,
      }),
    });
    $("projectNote").value = "";
    toast("项目进展已提交");
    await loadAll();
  } catch (err) {
    toast(err.message);
  }
});

$("researchForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/api/research-submissions", {
      method: "POST",
      body: JSON.stringify({
        user_id: currentUserId(),
        title: $("researchTitle").value,
        stage: $("researchStage").value,
        progress: Number($("researchProgress").value),
        note: $("researchNote").value,
      }),
    });
    $("researchNote").value = "";
    toast("科研进展已提交");
    await loadAll();
  } catch (err) {
    toast(err.message);
  }
});

$("adminLogin").addEventListener("click", async () => {
  try {
    state.adminPassword = $("adminPassword").value;
    const res = await api("/api/admin/login", {
      method: "POST",
      body: JSON.stringify({password: state.adminPassword}),
    });
    if (res.ok) {
      localStorage.setItem("adminPassword", state.adminPassword);
      $("adminContent").classList.remove("hidden");
      $("exportExcel").disabled = false;
      toast("管理员已登录");
    }
  } catch (err) {
    toast(err.message);
  }
});

$("userForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/api/admin/users", {method: "POST", body: JSON.stringify({name: $("newUserName").value})});
    $("newUserName").value = "";
    toast("人员已添加");
    await loadAll();
  } catch (err) {
    toast(err.message);
  }
});

$("projectAdminForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/api/admin/projects", {method: "POST", body: JSON.stringify({name: $("newProjectName").value})});
    $("newProjectName").value = "";
    toast("项目已添加");
    await loadAll();
  } catch (err) {
    toast(err.message);
  }
});

$("taskForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/api/admin/tasks", {
      method: "POST",
      body: JSON.stringify({
        project_id: Number($("newTaskProject").value),
        name: $("newTaskName").value,
        workload: Number($("newTaskWorkload").value),
      }),
    });
    $("newTaskName").value = "";
    toast("任务已添加");
    await loadAll();
  } catch (err) {
    toast(err.message);
  }
});

$("exportExcel").addEventListener("click", async () => {
  const res = await fetch("/api/export", {headers: {"X-Admin-Password": state.adminPassword}});
  if (!res.ok) {
    toast("导出失败");
    return;
  }
  const blob = await res.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `进展统计导出_${new Date().toISOString().slice(0, 10)}.xlsx`;
  link.click();
  URL.revokeObjectURL(link.href);
});

loadAll().catch((err) => toast(err.message));
