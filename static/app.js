const PROGRESS_OPTIONS = [20, 50, 70, 90, 100];

let state = {
  users: [],
  projects: [],
  tasks: [],
  stats: {},
  adminPassword: localStorage.getItem("adminPassword") || "",
};

const $ = (id) => document.getElementById(id);

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
  state = {...state, ...bootstrap, stats};
  renderAll();
}

function optionList(values, selected) {
  return values.map((value) => `<option value="${value}" ${String(value) === String(selected) ? "selected" : ""}>${value}%</option>`).join("");
}

function renderSelect(select, records, label = "name") {
  select.innerHTML = records
    .filter((item) => item.active !== 0)
    .map((item) => `<option value="${item.id}">${item[label]}</option>`)
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

function activeProjectTasks(projectId) {
  return state.tasks.filter((task) => task.active !== 0 && Number(task.project_id) === Number(projectId));
}

function renderUserView() {
  renderSelect($("currentUser"), state.users);
  renderSelect($("projectSelect"), state.projects);
  $("projectProgress").innerHTML = optionList(PROGRESS_OPTIONS, 20);
  $("researchProgress").innerHTML = optionList(PROGRESS_OPTIONS, 20);
  updateTaskSelect();
  renderMyHistory();
}

function updateTaskSelect() {
  renderSelect($("taskSelect"), activeProjectTasks($("projectSelect").value));
}

function renderMyHistory() {
  const user = state.users.find((item) => item.id === currentUserId());
  if (!user) return;
  const projectRows = (state.stats.project_history || []).filter((row) => row.user_name === user.name);
  const researchRows = (state.stats.research_history || []).filter((row) => row.user_name === user.name);
  table($("myProjectHistory"), ["时间", "项目", "任务", "进度", "备注"], projectRows, (row) => `
    <tr><td>${row.created_at}</td><td>${row.project_name}</td><td>${row.task_name}</td><td>${row.progress}%</td><td>${row.note || ""}</td></tr>
  `);
  table($("myResearchHistory"), ["时间", "标题", "阶段", "进度"], researchRows, (row) => `
    <tr><td>${row.created_at}</td><td>${row.title}</td><td>${row.stage}</td><td>${row.progress}%</td></tr>
  `);
}

function renderAdminView() {
  $("adminPassword").value = state.adminPassword;
  $("exportExcel").disabled = !state.adminPassword;
  renderSelect($("newTaskProject"), state.projects);
  renderUsers();
  renderProjects();
  renderTasks();
  renderStats();
}

function renderUsers() {
  $("userList").innerHTML = state.users.map((user) => `
    <div class="list-row">
      <input value="${user.name}" data-user-name="${user.id}">
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
      <input value="${project.name}" data-project-name="${project.id}">
      <select data-project-active="${project.id}">
        <option value="1" ${project.active ? "selected" : ""}>启用</option>
        <option value="0" ${!project.active ? "selected" : ""}>停用</option>
      </select>
      <button data-save-project="${project.id}">保存</button>
    </div>
  `).join("");
}

function renderTasks() {
  const rows = state.stats.task_rollup || [];
  table($("taskTable"), ["项目", "任务", "工作量", "状态", "累计填报", "次数", "确认进度", "操作"], rows, (row) => `
    <tr>
      <td>${row.project_name}</td>
      <td><input value="${row.task_name}" data-task-name="${row.id}"></td>
      <td><input type="number" min="0" step="0.1" value="${row.workload}" data-task-workload="${row.id}"></td>
      <td>
        <select data-task-active="${row.id}">
          <option value="1" ${row.active ? "selected" : ""}>启用</option>
          <option value="0" ${!row.active ? "selected" : ""}>停用</option>
        </select>
      </td>
      <td>${Number(row.submitted_progress).toFixed(1)}%</td>
      <td>${row.submission_count}</td>
      <td><input type="number" min="0" max="100" step="1" value="${row.confirmed_progress}" data-confirm="${row.id}"></td>
      <td>
        <button data-save-task="${row.id}">保存</button>
        <button data-confirm-task="${row.id}">确认</button>
      </td>
    </tr>
  `);
}

function renderStats() {
  table($("projectStats"), ["项目", "总工作量", "已确认工作量", "整体进度"], state.stats.project_progress || [], (row) => `
    <tr><td>${row.name}</td><td>${row.total_workload}</td><td>${Number(row.done_workload).toFixed(2)}</td><td>${row.progress}%</td></tr>
  `);
  table($("contributionStats"), ["姓名", "项目", "贡献工作量", "折算项目占比"], state.stats.contributions || [], (row) => `
    <tr><td>${row.user_name}</td><td>${row.project_name}</td><td>${row.contribution_workload}</td><td>${row.contribution_percent}%</td></tr>
  `);
  table($("researchStats"), ["姓名", "大论文标题", "阶段", "进度", "更新时间"], state.stats.research_latest || [], (row) => `
    <tr><td>${row.user_name}</td><td>${row.title}</td><td>${row.stage}</td><td>${row.progress}%</td><td>${row.created_at}</td></tr>
  `);
  table($("projectHistory"), ["时间", "姓名", "项目", "任务", "进度", "备注"], state.stats.project_history || [], (row) => `
    <tr><td>${row.created_at}</td><td>${row.user_name}</td><td>${row.project_name}</td><td>${row.task_name}</td><td>${row.progress}%</td><td>${row.note || ""}</td></tr>
  `);
  table($("researchHistory"), ["时间", "姓名", "标题", "阶段", "进度"], state.stats.research_history || [], (row) => `
    <tr><td>${row.created_at}</td><td>${row.user_name}</td><td>${row.title}</td><td>${row.stage}</td><td>${row.progress}%</td></tr>
  `);
}

function renderAll() {
  renderUserView();
  renderAdminView();
}

document.addEventListener("click", async (event) => {
  const tab = event.target.closest(".tab");
  if (tab) {
    document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
    document.querySelectorAll(".view").forEach((item) => item.classList.remove("active"));
    tab.classList.add("active");
    $(tab.dataset.view).classList.add("active");
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
});

$("projectSelect").addEventListener("change", updateTaskSelect);
$("currentUser").addEventListener("change", renderMyHistory);

$("projectForm").addEventListener("submit", async (event) => {
  event.preventDefault();
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
});

$("researchForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  await api("/api/research-submissions", {
    method: "POST",
    body: JSON.stringify({
      user_id: currentUserId(),
      title: $("researchTitle").value,
      stage: $("researchStage").value,
      progress: Number($("researchProgress").value),
    }),
  });
  toast("科研进展已提交");
  await loadAll();
});

$("adminLogin").addEventListener("click", async () => {
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
});

$("userForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  await api("/api/admin/users", {method: "POST", body: JSON.stringify({name: $("newUserName").value})});
  $("newUserName").value = "";
  toast("人员已添加");
  await loadAll();
});

$("projectAdminForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  await api("/api/admin/projects", {method: "POST", body: JSON.stringify({name: $("newProjectName").value})});
  $("newProjectName").value = "";
  toast("项目已添加");
  await loadAll();
});

$("taskForm").addEventListener("submit", async (event) => {
  event.preventDefault();
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
