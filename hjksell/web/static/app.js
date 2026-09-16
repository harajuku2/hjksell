const state = {
  portfolioId: null,
  filter: "all",
  telegramLive: false,
  telegramChannelDraft: null,
  telegramChannelDirty: false,
  rateDraft: null,
  rateDirty: false,
  openItemMenuId: null,
  view: "catalog"
};
const saleDrafts = new Map();
const monthlyDrafts = new Map();
const monthOpenState = new Map();
let collapsedSummaryPeriod = null;
const monthNames = [
  "ЯНВАРЬ", "ФЕВРАЛЬ", "МАРТ", "АПРЕЛЬ", "МАЙ", "ИЮНЬ",
  "ИЮЛЬ", "АВГУСТ", "СЕНТЯБРЬ", "ОКТЯБРЬ", "НОЯБРЬ", "ДЕКАБРЬ"
];

const portfolioSelect = document.querySelector("#portfolioSelect");
const photoViewer = document.querySelector("#photoViewer");
const photoViewerImage = document.querySelector("#photoViewerImage");
const rateInput = document.querySelector("#rateInput");
const message = document.querySelector("#message");
const catalogRoot = document.querySelector("#catalog");
const filters = document.querySelector("#filters");
const collapsedSummary = document.querySelector("#collapsedSummary");
const addItemButton = document.querySelector("#addItemButton");
const newItemPanel = document.querySelector("#newItemPanel");
const telegramButton = document.querySelector("#telegramButton");
const telegramPanel = document.querySelector("#telegramPanel");
const telegramForm = document.querySelector("#telegramForm");
const telegramToken = document.querySelector("#telegramToken");
const telegramChannel = document.querySelector("#telegramChannel");
const telegramStatus = document.querySelector("#telegramStatus");
const telegramHint = document.querySelector("#telegramHint");
const discoveredChannels = document.querySelector("#discoveredChannels");
const renamePortfolioButton = document.querySelector("#renamePortfolioButton");
const renamePortfolioForm = document.querySelector("#renamePortfolioForm");
const portfolioNameInput = document.querySelector("#portfolioNameInput");
const createPortfolioButton = document.querySelector("#createPortfolioButton");
const createPortfolioForm = document.querySelector("#createPortfolioForm");
const newPortfolioNameInput = document.querySelector("#newPortfolioNameInput");
const deletePortfolioButton = document.querySelector("#deletePortfolioButton");
const analyticsButton = document.querySelector("#analyticsButton");
const catalogView = document.querySelector("#catalogView");
const analyticsView = document.querySelector("#analyticsView");
const analyticsPeriod = document.querySelector("#analyticsPeriod");
const analyticsPeriodRange = document.querySelector("#analyticsPeriodRange");
const analyticsSections = document.querySelector("#analyticsSections");
const portfolioPicker = document.querySelector("#portfolioPicker");
const portfolioPickerButton = document.querySelector("#portfolioPickerButton");
const portfolioPickerLabel = document.querySelector("#portfolioPickerLabel");
const portfolioPickerMenu = document.querySelector("#portfolioPickerMenu");
const analyticsPicker = document.querySelector("#analyticsPicker");
const analyticsPickerButton = document.querySelector("#analyticsPickerButton");
const analyticsPickerLabel = document.querySelector("#analyticsPickerLabel");
const analyticsPickerMenu = document.querySelector("#analyticsPickerMenu");

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = `Ошибка ${response.status}`;
    try {
      const payload = await response.json();
      detail = typeof payload.detail === "string" ? payload.detail : detail;
    } catch (_) {
      // Keep the HTTP status when the response has no JSON body.
    }
    throw new Error(detail);
  }
  return response.json();
}

function jsonOptions(method, body) {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  };
}

function setMessage(text = "") {
  message.textContent = text;
}

function display(value, suffix = "") {
  return value === null || value === undefined ? "—" : `${value}${suffix}`;
}

function animateVisibility(element, show, onClosed = null) {
  if (show) {
    element.hidden = false;
    element.classList.remove("surface-exit", "surface-enter");
    void element.offsetWidth;
    element.classList.add("surface-enter");
    return;
  }
  if (element.hidden || element.classList.contains("surface-exit")) return;
  element.classList.remove("surface-enter");
  element.classList.add("surface-exit");
  const finishExit = (event) => {
    if (event.target !== element) return;
    element.removeEventListener("animationend", finishExit);
    element.hidden = true;
    element.classList.remove("surface-exit");
    onClosed?.();
  };
  element.addEventListener("animationend", finishExit);
}

function closeGlassSelects() {
  [
    [portfolioPickerButton, portfolioPickerMenu],
    [analyticsPickerButton, analyticsPickerMenu]
  ].forEach(([button, menu]) => {
    button.setAttribute("aria-expanded", "false");
    animateVisibility(menu, false);
  });
}

function renderGlassSelect(select, label, menu) {
  const selected = select.selectedOptions[0];
  label.textContent = selected?.textContent || "Выберите";
  menu.innerHTML = [...select.options].map((option) => `
    <button type="button" role="option" data-value="${escapeHtml(option.value)}" aria-selected="${option.selected}">
      ${escapeHtml(option.textContent)}
    </button>`).join("");
}

function toggleGlassSelect(button, menu) {
  const isOpening = menu.hidden || menu.classList.contains("surface-exit");
  closeGlassSelects();
  animateVisibility(menu, isOpening);
  button.setAttribute("aria-expanded", String(isOpening));
}

function togglePanel(panel, button) {
  const isOpening = panel.hidden || panel.classList.contains("surface-exit");
  animateVisibility(panel, isOpening);
  button.setAttribute("aria-expanded", String(isOpening));
  return isOpening;
}

function catalogIsBeingEdited() {
  const active = document.activeElement;
  return Boolean(
    active &&
    catalogRoot.contains(active) &&
    ["INPUT", "TEXTAREA", "SELECT"].includes(active.tagName)
  );
}

function monthStateKey(period) {
  return `${state.portfolioId}:${period}`;
}

function monthlyDraftKey(year, month) {
  return `${state.portfolioId}:${year}-${month}`;
}

function currentMonthGroup(months) {
  const today = new Date();
  return months.find((month) => month.year === today.getFullYear() && month.month === today.getMonth() + 1)
    || months[0]
    || null;
}

function collapsedSummaryHtml(group) {
  if (!group) return "";
  const metrics = group.metrics;
  return [
    [metrics.invested, "ВЛОЖЕНО", " BYN"],
    [metrics.purchased_count, "КУПЛЕНО", ""],
    [metrics.revenue, "ПРОДАЖИ", " BYN"],
    [metrics.sold_count, "ПРОДАНО", ""],
    [metrics.net_profit, "ЧИСТАЯ ПРИБЫЛЬ", " BYN"]
  ].map(([value, label, suffix], index) =>
    `<div class="summary-kpi${index === 4 ? " summary-kpi-profit" : ""}"><strong>${display(value, suffix)}</strong><span>${label}</span></div>`
  ).join("");
}

function updateCollapsedSummaryVisibility(group) {
  if (!group) {
    collapsedSummaryPeriod = null;
    collapsedSummary.hidden = true;
    return;
  }
  collapsedSummaryPeriod = `${group.year}-${group.month}`;
  const defaultOpen = group.year === new Date().getFullYear() && group.month === new Date().getMonth() + 1;
  const isOpen = monthOpenState.get(monthStateKey(collapsedSummaryPeriod)) ?? defaultOpen;
  collapsedSummary.hidden = isOpen;
}

function updateFilterIndicator() {
  const buttons = [...filters.querySelectorAll("button[data-filter]")];
  const activeIndex = buttons.findIndex((button) => button.dataset.filter === state.filter);
  filters.style.setProperty("--filter-index", String(Math.max(activeIndex, 0)));
}

function openPhotoViewer(photoUrl) {
  photoViewerImage.src = photoUrl;
  photoViewer.showModal();
}

function metricClass(value) {
  if (value === null || value === undefined || value === "" || value === "—") return "";
  const numeric = Number(String(value).replace(",", "."));
  if (!Number.isFinite(numeric) || numeric === 0) return "";
  return numeric < 0 ? "metric-negative" : "metric-positive";
}

const analyticsGroups = [
  {
    title: "РЕЗУЛЬТАТ",
    className: "analytics-result",
    metrics: [
      ["revenue", "ПРОДАЖИ", " BYN"],
      ["realized_profit", "ПРИБЫЛЬ ДО РАСХОДОВ", " BYN"],
      ["net_profit", "ЧИСТАЯ ПРИБЫЛЬ", " BYN"],
      ["expenses", "РАСХОДЫ", " BYN"],
      ["sold_count", "ПРОДАНО", ""]
    ]
  },
  {
    title: "ЭФФЕКТИВНОСТЬ",
    metrics: [
      ["roi", "ROI", "%"],
      ["roi_after_expenses", "ROI ПОСЛЕ РАСХОДОВ", "%"],
      ["average_x", "СРЕДНИЙ X", "x"],
      ["best_x", "ЛУЧШИЙ X", "x"],
      ["worst_x", "ХУДШИЙ X", "x"]
    ]
  },
  {
    title: "ЗАКУПКИ И СКЛАД",
    metrics: [
      ["invested", "ВЛОЖЕНО", " BYN"],
      ["purchased_count", "КУПЛЕНО", ""],
      ["in_stock_count", "В НАЛИЧИИ", ""],
      ["warehouse_value", "СТОИМОСТЬ НА СКЛАДЕ", " BYN"]
    ]
  },
  {
    title: "СРЕДНИЕ ПОКАЗАТЕЛИ",
    metrics: [
      ["average_cost", "СРЕДНЯЯ СЕБЕСТОИМОСТЬ", " BYN"],
      ["average_sale", "СРЕДНЯЯ ПРОДАЖА", " BYN"],
      ["average_profit", "СРЕДНЯЯ ПРИБЫЛЬ", " BYN"],
      ["average_sale_days", "СРЕДНЕЕ ВРЕМЯ ПРОДАЖИ", " дн."]
    ]
  }
];

function analyticsTone(key, value) {
  if (key === "expenses") return " analytics-metric-amber";
  if (["realized_profit", "net_profit", "roi", "roi_after_expenses", "average_profit"].includes(key)) {
    return ` ${metricClass(value)}`;
  }
  return "";
}

function analyticsHtml(metrics) {
  return analyticsGroups.map((group) => `
    <section class="analytics-group ${group.className || ""}">
      <h3>${group.title}</h3>
      <div class="analytics-grid">
        ${group.metrics.map(([key, label, suffix]) => `
          <article class="analytics-metric${key === "net_profit" ? " analytics-hero" : ""}${analyticsTone(key, metrics[key])}">
            <strong>${display(metrics[key], suffix)}</strong>
            <span>${label}</span>
          </article>`).join("")}
      </div>
    </section>`).join("");
}

let lastAnalyticsFingerprint = null;

async function loadAnalytics(force = false) {
  if (state.portfolioId === null) return;
  const portfolioId = state.portfolioId;
  const report = await api(`/api/analytics?portfolio_id=${portfolioId}&period=${analyticsPeriod.value}`);
  if (state.portfolioId !== portfolioId) return;
  const fingerprint = JSON.stringify(report);
  if (!force && fingerprint === lastAnalyticsFingerprint) return;
  lastAnalyticsFingerprint = fingerprint;
  analyticsPeriodRange.textContent = `${report.period.start} — ${report.period.end}`;
  analyticsSections.innerHTML = analyticsHtml(report.metrics);
}

async function setView(view) {
  state.view = view;
  const showAnalytics = view === "analytics";
  catalogView.hidden = showAnalytics;
  analyticsView.hidden = !showAnalytics;
  analyticsButton.setAttribute("aria-pressed", String(showAnalytics));
  analyticsButton.textContent = showAnalytics ? "Каталог" : "Аналитика";
  addItemButton.hidden = showAnalytics;
  telegramButton.hidden = showAnalytics;
  if (showAnalytics) await loadAnalytics(true);
}

function itemHtml(item) {
  const photo = item.photo_url
    ? `<button class="photo photo-button" type="button" data-action="view-photo" data-photo-url="${escapeHtml(item.photo_url)}" aria-label="Открыть фото вещи">
        <img src="${escapeHtml(item.photo_url)}" alt="Фото вещи">
      </button>`
    : `<div class="photo">Нет фото</div>`;
  const stateLabels = { in_stock: "В НАЛИЧИИ", sold: "ПРОДАНО", no_revenue: "УШЛА НА БЛАГОЕ ДЕЛО" };
  const profitClass = metricClass(item.profit);
  const saleValue = saleDrafts.has(item.id) ? saleDrafts.get(item.id) : (item.sale_price_byn ?? "");
  const itemMenuOpen = state.openItemMenuId === item.id;
  const saleDate = item.sale_date || "—";
  const saleDateDisabled = item.sale_date ? "" : " disabled";
  return `
    <article class="item item-${item.sale_state}${itemMenuOpen ? " is-menu-open" : ""}" data-item-id="${item.id}">
      ${photo}
      <div class="item-content">
        <dl class="item-data">
          <div><dt>Дата покупки</dt><dd class="item-date">${escapeHtml(item.purchase_date)}</dd></div>
          <div><dt>Покупка</dt><dd>${escapeHtml(item.purchase_price_pln)} PLN</dd></div>
          <div><dt>Себестоимость</dt><dd class="metric-cost">${escapeHtml(item.cost_byn)} BYN</dd></div>
          <div><dt>Курс</dt><dd>${escapeHtml(item.exchange_rate)}</dd></div>
          <div><dt>Статус</dt><dd class="item-status status-${item.sale_state}">${stateLabels[item.sale_state]}</dd></div>
          <div><dt>Прибыль</dt><dd class="metric-profit ${profitClass}">${display(item.profit, " BYN")}</dd></div>
          <div><dt>X</dt><dd class="${metricClass(item.x)}">${display(item.x, "x")}</dd></div>
          <div><dt>ROI</dt><dd class="${metricClass(item.roi)}">${display(item.roi, "%")}</dd></div>
          <div><dt>Дней до продажи</dt><dd>${display(item.days_to_sale)}</dd></div>
        </dl>
        <div class="item-footer">
          <form data-action="sale" data-item-id="${item.id}">
            <label>Продажа, BYN
              <input name="sale_price_byn" inputmode="decimal" value="${escapeHtml(saleValue)}" placeholder="пусто = отменить">
            </label>
            <button type="submit">Сохранить продажу</button>
          </form>
        </div>
      </div>
      <div class="item-menu-wrap">
        <button class="item-menu-button" type="button" data-action="menu" aria-expanded="${itemMenuOpen}" aria-label="Действия для вещи">⋯</button>
        <div class="item-menu"${itemMenuOpen ? "" : " hidden"}>
          <div class="menu-fields">
            <div class="menu-field-row">
              <div><span>Цена покупки</span><strong>${escapeHtml(item.purchase_price_pln)} PLN</strong></div>
              <button class="menu-edit-button" type="button" data-action="edit-item-field" data-field="purchase_price_pln" title="Изменить цену покупки" aria-label="Изменить цену покупки">✎</button>
            </div>
            <form class="item-editor" data-action="item-field" data-field="purchase_price_pln" data-item-id="${item.id}" hidden>
              <label>Цена покупки, PLN<input name="purchase_price_pln" inputmode="decimal" value="${escapeHtml(item.purchase_price_pln)}" required></label>
              <button type="submit">Сохранить</button>
            </form>
            <div class="menu-field-row">
              <div><span>Дата покупки</span><strong>${escapeHtml(item.purchase_date)}</strong></div>
              <button class="menu-edit-button" type="button" data-action="edit-item-field" data-field="purchase_date" title="Изменить дату покупки" aria-label="Изменить дату покупки">✎</button>
            </div>
            <form class="item-editor" data-action="item-field" data-field="purchase_date" data-item-id="${item.id}" hidden>
              <label>Дата покупки<input name="purchase_date" type="date" value="${escapeHtml(item.purchase_date)}" required></label>
              <button type="submit">Сохранить</button>
            </form>
            <div class="menu-field-row">
              <div><span>Курс покупки</span><strong>${escapeHtml(item.exchange_rate)}</strong></div>
              <button class="menu-edit-button" type="button" data-action="edit-item-field" data-field="exchange_rate" title="Изменить курс покупки" aria-label="Изменить курс покупки">✎</button>
            </div>
            <form class="item-editor" data-action="item-field" data-field="exchange_rate" data-item-id="${item.id}" hidden>
              <label>Курс покупки<input name="exchange_rate" inputmode="decimal" value="${escapeHtml(item.exchange_rate)}" required></label>
              <button type="submit">Сохранить</button>
            </form>
            <div class="menu-field-row">
              <div><span>Дата продажи</span><strong>${escapeHtml(saleDate)}</strong></div>
              <button class="menu-edit-button" type="button" data-action="edit-item-field" data-field="sale_date" title="${item.sale_date ? "Изменить дату продажи" : "Дата продажи появится после продажи"}" aria-label="${item.sale_date ? "Изменить дату продажи" : "Дата продажи недоступна"}"${saleDateDisabled}>✎</button>
            </div>
            <form class="item-editor" data-action="sale-date" data-item-id="${item.id}" hidden>
              <label>Дата продажи<input name="sale_date" type="date" value="${escapeHtml(item.sale_date || "")}" required></label>
              <button type="submit">Сохранить</button>
            </form>
          </div>
          <form data-action="photo" data-item-id="${item.id}">
            <label>Загрузить фото
              <span class="file-picker">
                <span data-file-name>Добавить фото</span>
                <input name="photo" type="file" required accept="image/jpeg,image/png,image/webp,image/gif,image/bmp">
              </span>
            </label>
            <button type="submit">Применить</button>
          </form>
          <button class="danger" type="button" data-action="delete" data-item-id="${item.id}">Удалить</button>
        </div>
      </div>
    </article>`;
}

function monthHtml(group) {
  const metrics = group.metrics;
  const today = new Date();
  const period = `${group.year}-${group.month}`;
  const defaultOpen = group.year === today.getFullYear() && group.month === today.getMonth() + 1;
  const isOpen = monthOpenState.get(monthStateKey(period)) ?? defaultOpen;
  const open = isOpen ? " open" : "";
  const kpis = [
    [metrics.invested, "ВЛОЖЕНО", " BYN"],
    [metrics.purchased_count, "КУПЛЕНО", ""],
    [metrics.revenue, "ПРОДАЖИ", " BYN"],
    [metrics.sold_count, "ПРОДАНО", ""],
    [metrics.average_x, "СРЕДНИЙ X", "x"],
    [metrics.roi, "ROI", "%"],
    [metrics.net_profit, "ЧИСТАЯ ПРИБЫЛЬ", " BYN"]
  ].map(([value, label, suffix]) =>
    `<div class="kpi"><strong>${display(value, suffix)}</strong><span>${label}</span></div>`
  ).join("");
  const items = group.items.length ? group.items.map(itemHtml).join("") : `<p class="empty">Нет вещей по выбранному фильтру.</p>`;
  const monthlyKey = monthlyDraftKey(group.year, group.month);
  const monthlyDraft = monthlyDrafts.get(monthlyKey) || {};
  const expenses = monthlyDraft.expenses ?? group.values.expenses;
  const otherIncome = monthlyDraft.other_income ?? group.values.other_income;
  const advertising = monthlyDraft.advertising ?? group.values.advertising;
  return `
    <details class="month" data-period="${period}"${open}>
      <summary>${monthNames[group.month - 1]} ${group.year}</summary>
      <div class="month-body">
        <div class="kpis">${kpis}</div>
        <form class="monthly-values" data-action="monthly" data-year="${group.year}" data-month="${group.month}">
          <label>РАСХОДЫ, BYN<input name="expenses" inputmode="decimal" value="${escapeHtml(expenses)}" required></label>
          <label>ДРУГИЕ ДОХОДЫ, BYN<input name="other_income" inputmode="decimal" value="${escapeHtml(otherIncome)}" required></label>
          <label>РЕКЛАМА, BYN<input name="advertising" inputmode="decimal" value="${escapeHtml(advertising)}" required></label>
          <button type="submit">Сохранить месяц</button>
        </form>
        <div class="items">${items}</div>
      </div>
    </details>`;
}

async function loadPortfolios(preferredId = state.portfolioId) {
  const portfolios = await api("/api/portfolios");
  portfolioSelect.replaceChildren(...portfolios.map((portfolio) => {
    const option = document.createElement("option");
    option.value = portfolio.id;
    option.textContent = portfolio.name;
    return option;
  }));
  if (!portfolios.length) throw new Error("Нет доступных портфелей.");
  state.portfolioId = portfolios.some((portfolio) => Number(portfolio.id) === Number(preferredId))
    ? Number(preferredId)
    : Number(portfolios[0].id);
  portfolioSelect.value = String(state.portfolioId);
  portfolioNameInput.value = portfolios.find((portfolio) => Number(portfolio.id) === state.portfolioId).name;
  renderGlassSelect(portfolioSelect, portfolioPickerLabel, portfolioPickerMenu);
}

async function loadCatalog(force = false) {
  if (state.portfolioId === null) return;
  if (!force && (catalogIsBeingEdited() || saleDrafts.size || monthlyDrafts.size || state.openItemMenuId !== null)) return;
  const portfolioId = state.portfolioId;
  const filter = state.filter;
  setMessage();
  const data = await api(`/api/catalog?portfolio_id=${portfolioId}&filter=${filter}`);
  if (state.portfolioId !== portfolioId || state.filter !== filter) return;
  const fingerprint = JSON.stringify(data);
  if (!force && fingerprint === lastCatalogFingerprint) return;
  lastCatalogFingerprint = fingerprint;
  if (!state.rateDirty && (force || document.activeElement !== rateInput)) rateInput.value = data.exchange_rate;
  const summaryGroup = currentMonthGroup(data.months);
  collapsedSummary.innerHTML = collapsedSummaryHtml(summaryGroup);
  catalogRoot.querySelectorAll(".month").forEach((month) => {
    monthOpenState.set(monthStateKey(month.dataset.period), month.open);
  });
  catalogRoot.innerHTML = data.months.map(monthHtml).join("");
  updateCollapsedSummaryVisibility(summaryGroup);
}

async function loadTelegramStatus(force = false) {
  if (state.portfolioId === null) return;
  const portfolioId = state.portfolioId;
  const status = await api(`/api/telegram/status?portfolio_id=${portfolioId}`);
  if (state.portfolioId !== portfolioId) return;
  state.telegramLive = status.running;
  if (force || !state.telegramChannelDirty) {
    telegramChannel.value = status.channel_id ?? "";
    state.telegramChannelDraft = telegramChannel.value;
    state.telegramChannelDirty = false;
  }
  const lastMessage = status.last_message || "";
  if (status.last_status === "error") {
    telegramStatus.textContent = "Ошибка Telegram";
    telegramStatus.className = "telegram-status status-negative";
    telegramHint.textContent = lastMessage || "Не удалось связаться с Telegram API.";
  } else if (status.running && status.configured) {
    telegramStatus.textContent = "Подключён";
    telegramStatus.className = "telegram-status status-positive";
    telegramHint.textContent = status.last_status === "imported" || status.last_status === "duplicate"
      ? lastMessage
      : "Канал привязан. Новые публикации будут импортироваться автоматически.";
  } else if (status.running && status.discovered_channels.length) {
    telegramStatus.textContent = "Канал обнаружен";
    telegramStatus.className = "telegram-status status-warning";
    telegramHint.textContent = "Выберите канал и нажмите «Сохранить и запустить».";
  } else if (status.running) {
    telegramStatus.textContent = "Ожидает публикации";
    telegramStatus.className = "telegram-status status-warning";
    telegramHint.textContent = status.last_status === "ignored" && lastMessage
      ? lastMessage
      : "Отправьте в канал одну фотографию с ценой в PLN, чтобы обнаружить его.";
  } else {
    telegramStatus.textContent = status.channel_id ? "Остановлен" : "Не настроен";
    telegramStatus.className = "telegram-status";
    telegramHint.textContent = status.channel_id
      ? "Telegram-процесс остановлен. Сохраните настройки, чтобы запустить его снова."
      : "Введите токен бота и сохраните настройки.";
  }
  discoveredChannels.hidden = !status.discovered_channels.length;
  discoveredChannels.innerHTML = status.discovered_channels.length
    ? `<strong>Обнаруженные каналы</strong>${status.discovered_channels.map((channel) => `
        <button type="button" data-channel-id="${escapeHtml(channel.channel_id)}">${escapeHtml(channel.title || channel.channel_id)}</button>`).join("")}`
    : "";
}

async function switchPortfolio(portfolioId) {
  state.portfolioId = portfolioId;
  state.telegramChannelDraft = null;
  state.telegramChannelDirty = false;
  state.rateDraft = null;
  state.rateDirty = false;
  state.openItemMenuId = null;
  saleDrafts.clear();
  monthlyDrafts.clear();
  portfolioSelect.value = String(portfolioId);
  portfolioNameInput.value = portfolioSelect.selectedOptions[0].textContent;
  renderGlassSelect(portfolioSelect, portfolioPickerLabel, portfolioPickerMenu);
  try {
    await loadCatalog(true);
    await loadTelegramStatus(true);
    if (state.view === "analytics") await loadAnalytics();
  } catch (error) { setMessage(error.message); }
}

portfolioSelect.addEventListener("change", () => switchPortfolio(Number(portfolioSelect.value)));

portfolioPickerButton.addEventListener("click", () => toggleGlassSelect(portfolioPickerButton, portfolioPickerMenu));
portfolioPickerMenu.addEventListener("click", (event) => {
  const option = event.target.closest("button[data-value]");
  if (!option) return;
  portfolioSelect.value = option.dataset.value;
  renderGlassSelect(portfolioSelect, portfolioPickerLabel, portfolioPickerMenu);
  closeGlassSelects();
  switchPortfolio(Number(option.dataset.value));
});

analyticsPickerButton.addEventListener("click", () => toggleGlassSelect(analyticsPickerButton, analyticsPickerMenu));
analyticsPickerMenu.addEventListener("click", (event) => {
  const option = event.target.closest("button[data-value]");
  if (!option) return;
  analyticsPeriod.value = option.dataset.value;
  renderGlassSelect(analyticsPeriod, analyticsPickerLabel, analyticsPickerMenu);
  closeGlassSelects();
  analyticsPeriod.dispatchEvent(new Event("change"));
});

analyticsButton.addEventListener("click", async () => {
  try { await setView(state.view === "catalog" ? "analytics" : "catalog"); }
  catch (error) { setMessage(error.message); }
});

analyticsPeriod.addEventListener("change", async () => {
  renderGlassSelect(analyticsPeriod, analyticsPickerLabel, analyticsPickerMenu);
  lastAnalyticsFingerprint = null;
  try { await loadAnalytics(true); } catch (error) { analyticsSections.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`; }
});

addItemButton.addEventListener("click", () => {
  const isOpening = togglePanel(newItemPanel, addItemButton);
  if (isOpening) {
    document.querySelector('#itemForm [name="purchase_price_pln"]').focus();
  }
});

renamePortfolioButton.addEventListener("click", () => {
  renamePortfolioForm.hidden = !renamePortfolioForm.hidden;
  createPortfolioForm.hidden = true;
  if (!renamePortfolioForm.hidden) {
    portfolioNameInput.value = portfolioSelect.selectedOptions[0].textContent;
    portfolioNameInput.focus();
    portfolioNameInput.select();
  }
});

document.querySelector("#cancelRenameButton").addEventListener("click", () => {
  renamePortfolioForm.hidden = true;
});

createPortfolioButton.addEventListener("click", () => {
  const isOpening = createPortfolioForm.hidden;
  createPortfolioForm.hidden = !isOpening;
  renamePortfolioForm.hidden = true;
  if (isOpening) {
    newPortfolioNameInput.value = "";
    newPortfolioNameInput.focus();
  }
});

document.querySelector("#cancelCreatePortfolioButton").addEventListener("click", () => {
  createPortfolioForm.hidden = true;
});

createPortfolioForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const created = await api("/api/portfolios", jsonOptions("POST", { name: newPortfolioNameInput.value }));
    await loadPortfolios(created.id);
    createPortfolioForm.hidden = true;
    await switchPortfolio(created.id);
    setMessage(`Портфель «${created.name}» добавлен.`);
  } catch (error) { setMessage(error.message); }
});

renamePortfolioForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const renamed = await api(`/api/portfolios/${state.portfolioId}`, jsonOptions("PUT", { name: portfolioNameInput.value }));
    portfolioSelect.selectedOptions[0].textContent = renamed.name;
    portfolioNameInput.value = renamed.name;
    renderGlassSelect(portfolioSelect, portfolioPickerLabel, portfolioPickerMenu);
    renamePortfolioForm.hidden = true;
    setMessage();
  } catch (error) { setMessage(error.message); }
});

deletePortfolioButton.addEventListener("click", async () => {
  const portfolioName = portfolioSelect.selectedOptions[0]?.textContent || "текущий портфель";
  if (!window.confirm(`Удалить портфель «${portfolioName}» и все его данные?`)) return;
  try {
    await api(`/api/portfolios/${state.portfolioId}`, { method: "DELETE" });
    closeGlassSelects();
    renamePortfolioForm.hidden = true;
    createPortfolioForm.hidden = true;
    await loadPortfolios();
    await switchPortfolio(state.portfolioId);
    setMessage(`Портфель «${portfolioName}» удалён.`);
  } catch (error) { setMessage(error.message); }
});

telegramButton.addEventListener("click", async () => {
  const isOpening = togglePanel(telegramPanel, telegramButton);
  if (isOpening) {
    try { await loadTelegramStatus(); } catch (error) { setMessage(error.message); }
  }
});

telegramForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/api/telegram/config", jsonOptions("PUT", {
      portfolio_id: state.portfolioId,
      token: telegramToken.value.trim() || null,
      channel_id: telegramChannel.value.trim() || null
    }));
    telegramToken.value = "";
    state.telegramChannelDraft = null;
    state.telegramChannelDirty = false;
    await loadTelegramStatus(true);
    setMessage("Telegram сохранён.");
  } catch (error) { setMessage(error.message); }
});

document.querySelector("#telegramValidateButton").addEventListener("click", async () => {
  const token = telegramToken.value.trim();
  if (!token) {
    setMessage("Введите токен бота для проверки.");
    return;
  }
  const button = document.querySelector("#telegramValidateButton");
  button.disabled = true;
  telegramHint.textContent = "Проверка подключения к Telegram…";
  try {
    const result = await api("/api/telegram/validate", jsonOptions("POST", { token }));
    telegramHint.textContent = `Токен действителен: ${result.username ? `@${result.username}` : result.name}. Нажмите «Сохранить и запустить».`;
    setMessage("Токен Telegram действителен.");
  } catch (error) {
    telegramHint.textContent = error.message;
    setMessage(error.message);
  } finally {
    button.disabled = false;
  }
});

document.querySelector("#telegramClearButton").addEventListener("click", async () => {
  if (!window.confirm("Очистить токен, канал и состояние Telegram для этого портфеля?")) return;
  const button = document.querySelector("#telegramClearButton");
  button.disabled = true;
  try {
    await api(`/api/telegram/config?portfolio_id=${state.portfolioId}`, { method: "DELETE" });
    telegramToken.value = "";
    state.telegramChannelDraft = null;
    state.telegramChannelDirty = false;
    await loadTelegramStatus(true);
    setMessage("Настройки Telegram очищены.");
  } catch (error) {
    setMessage(error.message);
  } finally {
    button.disabled = false;
  }
});

discoveredChannels.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-channel-id]");
  if (!button) return;
  telegramChannel.value = button.dataset.channelId;
  state.telegramChannelDraft = telegramChannel.value;
  state.telegramChannelDirty = true;
  telegramHint.textContent = "Канал выбран. Нажмите «Сохранить и запустить».";
});

telegramChannel.addEventListener("input", () => {
  state.telegramChannelDraft = telegramChannel.value;
  state.telegramChannelDirty = true;
});

catalogRoot.addEventListener("input", (event) => {
  const input = event.target;
  const form = input.form;
  if (!form) return;
  if (form.dataset.action === "sale") {
    saleDrafts.set(Number(form.dataset.itemId), input.value);
  } else if (form.dataset.action === "monthly") {
    const key = monthlyDraftKey(form.dataset.year, form.dataset.month);
    const current = monthlyDrafts.get(key) || {};
    monthlyDrafts.set(key, { ...current, [input.name]: input.value });
  }
});

document.addEventListener("change", (event) => {
  const input = event.target;
  if (!(input instanceof HTMLInputElement) || input.type !== "file") return;
  const name = input.files?.[0]?.name || "Добавить фото";
  const label = input.closest(".file-picker")?.querySelector("[data-file-name]");
  if (label) label.textContent = name;
});

catalogRoot.addEventListener("toggle", (event) => {
  const month = event.target;
  if (!(month instanceof HTMLDetailsElement) || !month.classList.contains("month")) return;
  monthOpenState.set(monthStateKey(month.dataset.period), month.open);
  if (month.dataset.period === collapsedSummaryPeriod) collapsedSummary.hidden = month.open;
}, true);

filters.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-filter]");
  if (!button) return;
  state.filter = button.dataset.filter;
  filters.querySelectorAll("button").forEach((current) => {
    current.setAttribute("aria-pressed", String(current === button));
  });
  updateFilterIndicator();
  try { await loadCatalog(true); } catch (error) { setMessage(error.message); }
});

document.querySelector("#rateForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/api/settings/exchange-rate", jsonOptions("PUT", { rate: rateInput.value }));
    state.rateDraft = null;
    state.rateDirty = false;
    rateInput.blur();
    await loadCatalog(true);
  } catch (error) { setMessage(error.message); }
});

document.querySelector("#itemForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  try {
    const item = await api("/api/items", jsonOptions("POST", {
      portfolio_id: state.portfolioId,
      purchase_price_pln: data.get("purchase_price_pln"),
      purchase_date: data.get("purchase_date")
    }));
    const photo = data.get("photo");
    if (photo && photo.size) {
      await api(`/api/items/${item.id}/photo?portfolio_id=${state.portfolioId}&filename=${encodeURIComponent(photo.name)}`, {
        method: "POST", headers: { "Content-Type": photo.type }, body: photo
      });
    }
    form.reset();
    form.elements.purchase_date.valueAsDate = new Date();
    await loadCatalog(true);
  } catch (error) { setMessage(error.message); }
});

catalogRoot.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.target;
  try {
    if (form.dataset.action === "monthly") {
      const data = new FormData(form);
      const monthlyKey = monthlyDraftKey(form.dataset.year, form.dataset.month);
      await api("/api/monthly-values", jsonOptions("PUT", {
        portfolio_id: state.portfolioId,
        year: Number(form.dataset.year),
        month: Number(form.dataset.month),
        expenses: data.get("expenses"),
        other_income: data.get("other_income"),
        advertising: data.get("advertising")
      }));
      monthlyDrafts.delete(monthlyKey);
    } else if (form.dataset.action === "sale") {
      const data = new FormData(form);
      await api(`/api/items/${form.dataset.itemId}/sale`, jsonOptions("PUT", {
        portfolio_id: state.portfolioId,
        sale_price_byn: data.get("sale_price_byn")
      }));
      saleDrafts.delete(Number(form.dataset.itemId));
    } else if (form.dataset.action === "item-field") {
      const data = new FormData(form);
      const field = form.dataset.field;
      await api(`/api/items/${form.dataset.itemId}`, jsonOptions("PUT", {
        portfolio_id: state.portfolioId,
        [field]: data.get(field)
      }));
    } else if (form.dataset.action === "sale-date") {
      const data = new FormData(form);
      await api(`/api/items/${form.dataset.itemId}/sale-date`, jsonOptions("PUT", {
        portfolio_id: state.portfolioId,
        sale_date: data.get("sale_date")
      }));
    } else if (form.dataset.action === "photo") {
      const photo = new FormData(form).get("photo");
      await api(`/api/items/${form.dataset.itemId}/photo?portfolio_id=${state.portfolioId}&filename=${encodeURIComponent(photo.name)}`, {
        method: "POST", headers: { "Content-Type": photo.type }, body: photo
      });
    }
    await loadCatalog(true);
  } catch (error) { setMessage(error.message); }
});

catalogRoot.addEventListener("click", async (event) => {
  const photoButton = event.target.closest('button[data-action="view-photo"]');
  if (photoButton) {
    openPhotoViewer(photoButton.dataset.photoUrl);
    return;
  }
  const editButton = event.target.closest('button[data-action="edit-item-field"]');
  if (editButton) {
    const menu = editButton.closest(".item-menu");
    const field = editButton.dataset.field;
    menu.querySelectorAll(".item-editor").forEach((editor) => { editor.hidden = true; });
    const editor = field === "sale_date"
      ? menu.querySelector('form[data-action="sale-date"]')
      : menu.querySelector(`form[data-action="item-field"][data-field="${field}"]`);
    if (editor) {
      editor.hidden = false;
      editor.querySelector("input")?.focus();
    }
    return;
  }
  const menuButton = event.target.closest('button[data-action="menu"]');
  if (menuButton) {
    const menu = menuButton.nextElementSibling;
    const item = menuButton.closest(".item");
    const itemId = Number(menuButton.closest("[data-item-id]").dataset.itemId);
    const isOpening = menu.hidden || menu.classList.contains("surface-exit");
    state.openItemMenuId = isOpening ? itemId : null;
    document.querySelectorAll(".item-menu").forEach((currentMenu) => {
      if (currentMenu === menu) return;
      animateVisibility(currentMenu, false, () => currentMenu.closest(".item")?.classList.remove("is-menu-open"));
      currentMenu.previousElementSibling?.setAttribute("aria-expanded", "false");
    });
    if (isOpening) item.classList.add("is-menu-open");
    animateVisibility(menu, isOpening, () => item.classList.remove("is-menu-open"));
    menuButton.setAttribute("aria-expanded", String(isOpening));
    return;
  }
  const button = event.target.closest('button[data-action="delete"]');
  if (!button || !window.confirm("Удалить эту вещь? Она будет исключена из всей статистики.")) return;
  try {
    await api(`/api/items/${button.dataset.itemId}?portfolio_id=${state.portfolioId}`, { method: "DELETE" });
    state.openItemMenuId = null;
    saleDrafts.delete(Number(button.dataset.itemId));
    await loadCatalog(true);
  } catch (error) { setMessage(error.message); }
});

document.addEventListener("click", (event) => {
  if (!event.target.closest(".glass-select")) closeGlassSelects();
  if (event.target.closest(".item-menu-wrap")) return;
  if (state.openItemMenuId === null) return;
  state.openItemMenuId = null;
  document.querySelectorAll(".item-menu").forEach((menu) => {
    animateVisibility(menu, false, () => menu.closest(".item")?.classList.remove("is-menu-open"));
  });
  document.querySelectorAll(".item-menu-button").forEach((button) => {
    button.setAttribute("aria-expanded", "false");
  });
});

photoViewer.addEventListener("click", () => photoViewer.close());
photoViewer.addEventListener("close", () => photoViewerImage.removeAttribute("src"));

rateInput.addEventListener("input", () => {
  state.rateDraft = rateInput.value;
  state.rateDirty = true;
});

let liveRefreshBusy = false;
let lastCatalogFingerprint = null;
setInterval(async () => {
  if (document.hidden || !state.telegramLive || state.portfolioId === null || liveRefreshBusy) return;
  liveRefreshBusy = true;
  try {
    await loadCatalog();
    await loadTelegramStatus();
    if (state.view === "analytics") await loadAnalytics();
  } catch (error) { setMessage(error.message); }
  liveRefreshBusy = false;
}, 2000);

document.addEventListener("DOMContentLoaded", async () => {
  document.querySelector('#itemForm [name="purchase_date"]').valueAsDate = new Date();
  updateFilterIndicator();
  renderGlassSelect(analyticsPeriod, analyticsPickerLabel, analyticsPickerMenu);
  try {
    await loadPortfolios();
    await loadCatalog();
    await loadTelegramStatus();
  } catch (error) { setMessage(error.message); }
});
