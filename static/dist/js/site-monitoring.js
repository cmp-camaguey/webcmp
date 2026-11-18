/**
 * Monitoreo del sitio — auto-refresh del panel.
 *
 * El servidor pinta la primera foto completa. Este archivo sólo vuelve a pedir
 * el mismo snapshot cada pocos segundos y reemplaza los valores del DOM, sin
 * recargar la página ni reconstruir las tarjetas.
 *
 * Reglas de la casa:
 * - JS vanilla, sin dependencias ni build.
 * - Los números se formatean igual que en la plantilla (misma cantidad de
 *   decimales), para que el valor no "salte" al llegar el primer refresco.
 * - Todo texto que viene del servidor se escribe con textContent: una ruta con
 *   caracteres raros no puede inyectar HTML.
 */
;(function () {
  'use strict'

  var root = document.getElementById('monitoringRoot')
  if (!root) return

  var endpoint = root.getAttribute('data-url')
  var interval = parseInt(root.getAttribute('data-refresh-ms'), 10) || 5000
  var toggleButton = document.getElementById('monitoringToggle')
  var refreshButton = document.getElementById('monitoringRefresh')

  var EMPTY = '\u2014'
  var COLORS = ['success', 'warning', 'danger', 'primary', 'info', 'secondary']
  var STATE_COLORS = {
    ok: 'success',
    good: 'success',
    degraded: 'warning',
    'needs-improvement': 'warning',
    down: 'danger',
    poor: 'danger',
    nodata: 'secondary'
  }

  var timer = null
  var paused = false
  var inFlight = false
  // Aviso de estado degradado: se cierra con la X o solo a los 20 s, y una vez
  // cerrado no revive en cada refresco (solo si el estado empeora a "down").
  var ALERT_AUTO_HIDE_MS = 20000
  var alertAutoHideTimer = null
  var alertDismissed = false
  var alertLevel = ''

  function get(obj, path) {
    return path.split('.').reduce(function (acc, key) {
      if (acc === null || acc === undefined) return undefined
      return acc[key]
    }, obj)
  }

  function toNumber(value) {
    if (value === null || value === undefined || value === '') return null
    var number = Number(value)
    return isNaN(number) ? null : number
  }

  function clampPercent(value) {
    var number = toNumber(value)
    if (number === null) return null
    return Math.max(0, Math.min(100, number))
  }

  function trimZeros(text) {
    return text.replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1')
  }

  var formatters = {
    text: function (value) {
      return value === null || value === undefined || value === '' ? EMPTY : String(value)
    },
    int: function (value) {
      var number = toNumber(value)
      return number === null ? EMPTY : number.toLocaleString('es-MX', { maximumFractionDigits: 0 })
    },
    num1: function (value) {
      var number = toNumber(value)
      return number === null
        ? EMPTY
        : number.toLocaleString('es-MX', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
    },
    num2: function (value) {
      var number = toNumber(value)
      return number === null
        ? EMPTY
        : number.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    },
    pct: function (value) {
      var number = toNumber(value)
      return number === null ? EMPTY : trimZeros(number.toFixed(2)) + '%'
    },
    ms: function (value) {
      var number = toNumber(value)
      return number === null ? EMPTY : Math.round(number) + ' ms'
    }
  }

  function format(value, kind) {
    var formatter = formatters[kind] || formatters.text
    return formatter(value)
  }

  function replaceColorClasses(element, prefix, color) {
    COLORS.forEach(function (name) {
      element.classList.remove(prefix + name)
      element.classList.remove(prefix + name + '-lt')
    })
    element.classList.add(prefix + color)
  }

  function setBadge(element, color) {
    COLORS.forEach(function (name) {
      element.classList.remove('bg-' + name)
      element.classList.remove('bg-' + name + '-lt')
    })
    element.classList.add('bg-' + color + '-lt')
  }

  function setBarColor(element, color) {
    COLORS.forEach(function (name) {
      element.classList.remove('bg-' + name)
    })
    element.classList.add('bg-' + color)
  }

  function barColor(kind, value) {
    var number = toNumber(value)
    if (number === null) return 'secondary'
    if (kind === 'swap') return number >= 50 ? 'warning' : 'success'
    if (number >= 90) return 'danger'
    if (number >= 70) return 'warning'
    return 'success'
  }

  function coreColor(value) {
    var number = toNumber(value) || 0
    if (number >= 90) return 'danger'
    if (number >= 70) return 'warning'
    return 'primary'
  }

  function escapeAttribute(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
  }

  function applyValues(snapshot) {
    document.querySelectorAll('[data-live]').forEach(function (element) {
      var value = get(snapshot, element.getAttribute('data-live'))
      if (value === undefined) return
      element.textContent = format(value, element.getAttribute('data-fmt'))
    })

    document.querySelectorAll('[data-live-width]').forEach(function (element) {
      var percent = clampPercent(get(snapshot, element.getAttribute('data-live-width')))
      if (percent === null) {
        element.style.width = '0%'
        return
      }
      element.style.width = percent + '%'
      var kind = element.getAttribute('data-live-class')
      if (kind) setBarColor(element, barColor(kind, percent))
    })
  }

  function hideStatusAlert(alert) {
    alert.classList.add('d-none')
    if (alertAutoHideTimer !== null) {
      window.clearTimeout(alertAutoHideTimer)
      alertAutoHideTimer = null
    }
  }

  function dismissStatusAlert(alert) {
    alertDismissed = true
    hideStatusAlert(alert)
  }

  function showStatusAlert(alert) {
    alert.classList.remove('d-none')
    if (alertAutoHideTimer !== null) window.clearTimeout(alertAutoHideTimer)
    alertAutoHideTimer = window.setTimeout(function () {
      alertAutoHideTimer = null
      dismissStatusAlert(alert)
    }, ALERT_AUTO_HIDE_MS)
  }

  function initStatusAlert() {
    var alert = document.querySelector('[data-status-alert]')
    if (!alert) return
    var close = alert.querySelector('[data-status-alert-close]')
    if (close) {
      close.addEventListener('click', function () {
        dismissStatusAlert(alert)
      })
    }
    // El HTML del servidor puede traer el aviso visible: se arma el cierre
    // automatico sin esperar al primer refresco.
    if (!alert.classList.contains('d-none')) showStatusAlert(alert)
  }

  function applyStatus(snapshot) {
    var status = snapshot.status || {}
    var color = STATE_COLORS[status.level] || 'secondary'

    var label = document.querySelector('[data-status-label]')
    if (label) label.textContent = status.label || EMPTY

    var badge = document.querySelector('[data-status-badge]')
    if (badge) {
      setBadge(badge, color)
      badge.textContent = status.level || EMPTY
    }

    var reasons = status.reasons || []
    var level = status.level || ''
    var alert = document.querySelector('[data-status-alert]')
    if (alert) {
      var alertTitle = alert.querySelector('[data-status-alert-title]')
      var list = alert.querySelector('[data-status-reasons]')
      if (alertTitle) alertTitle.textContent = 'Estado ' + (status.label || EMPTY)
      if (list) {
        list.textContent = ''
        reasons.forEach(function (reason) {
          var item = document.createElement('li')
          item.textContent = reason
          list.appendChild(item)
        })
      }
      alert.classList.remove('alert-danger', 'alert-warning')
      alert.classList.add(level === 'down' ? 'alert-danger' : 'alert-warning')

      // Un aviso cerrado no vuelve en cada refresco: se muestra de nuevo solo
      // cuando se recupera y hay un incidente nuevo, o cuando empeora a "down".
      var escalated = alertLevel !== 'down' && level === 'down'
      alertLevel = level
      if (reasons.length === 0) {
        alertDismissed = false
        hideStatusAlert(alert)
      } else if (escalated) {
        alertDismissed = false
        showStatusAlert(alert)
      } else if (alertDismissed) {
        hideStatusAlert(alert)
      } else if (alert.classList.contains('d-none')) {
        showStatusAlert(alert)
      }
    }

    var incident = document.querySelector('[data-incident-line]')
    if (incident) {
      if (snapshot.incident && snapshot.incident.active) {
        incident.innerHTML =
          '<span class="text-danger"><i class="icon ti ti-alert-triangle"></i> ' +
          'Incidente activo: ' +
          escapeAttribute(snapshot.incident.duration_display || EMPTY) +
          '</span>'
      } else {
        incident.textContent = 'Sin incidentes activos'
      }
    }
  }

  function applyDependencies(snapshot) {
    document.querySelectorAll('[data-state-badge]').forEach(function (element) {
      var path = element.getAttribute('data-state-badge')
      var ok = get(snapshot, path) === true
      var color = ok ? 'success' : path === 'health.queue.ok' ? 'warning' : 'danger'
      setBadge(element, color)
      element.textContent =
        path === 'health.queue.ok'
          ? ok
            ? 'Al día'
            : 'Atrasado'
          : ok
            ? 'Responde'
            : 'No responde'
    })
  }

  function slotTitle(slot) {
    return slot.label + ' \u00b7 ' + slot.total + ' peticiones \u00b7 ' + slot.errors + ' errores'
  }

  function slotsMarkup(slots) {
    return slots
      .map(function (slot) {
        return (
          '<div class="tracking-block bg-' +
          (STATE_COLORS[slot.state] || 'secondary') +
          '" aria-hidden="true" data-bs-toggle="tooltip" data-bs-placement="top"' +
          ' data-bs-original-title="' +
          escapeAttribute(slotTitle(slot)) +
          '"></div>'
        )
      })
      .join('')
  }

  function applyUptimeSlots(snapshot) {
    var container = document.querySelector('[data-uptime-slots]')
    var slots = snapshot.uptime && snapshot.uptime.slots
    if (!container || !Array.isArray(slots)) return
    // El template invierte la lista (ahora primero); el refresco debe
    // mantener el mismo orden o los bloques se vuelven a poner al revés.
    var ordered = slots.slice().reverse()
    // Los tooltips los crea tabler.min.js al cargar sobre cada
    // [data-bs-toggle="tooltip"], y `window.bootstrap` no queda expuesto: una
    // reconstruccion con `innerHTML` dejaria los bloques sin tooltip. Si la
    // cantidad no cambio se actualizan en su lugar y las instancias de Tabler
    // siguen sirviendo, porque Bootstrap lee el title al abrir el tooltip.
    var blocks = container.querySelectorAll('.tracking-block')
    if (blocks.length !== ordered.length) {
      container.innerHTML = slotsMarkup(ordered)
      return
    }
    ordered.forEach(function (slot, index) {
      var block = blocks[index]
      replaceColorClasses(block, 'bg-', STATE_COLORS[slot.state] || 'secondary')
      block.setAttribute('data-bs-original-title', slotTitle(slot))
    })
  }

  function coreTitle(value, index) {
    return 'N\u00facleo ' + (index + 1) + ': ' + value + '%'
  }

  function coresMarkup(cores) {
    return cores
      .map(function (value, index) {
        return (
          '<span class="monitoring-core" aria-hidden="true" data-bs-toggle="tooltip"' +
          ' data-bs-placement="top" data-bs-original-title="' +
          escapeAttribute(coreTitle(value, index)) +
          '"><span class="monitoring-core-bar bg-' +
          coreColor(value) +
          '" style="height: ' +
          Math.max(0, Math.min(100, Number(value) || 0)) +
          '%"></span></span>'
        )
      })
      .join('')
  }

  function applyCores(snapshot) {
    var container = document.querySelector('[data-cores]')
    var cpu = snapshot.system && snapshot.system.cpu
    if (!container || !cpu || !Array.isArray(cpu.cores)) return
    var cores = container.querySelectorAll('.monitoring-core')
    if (cores.length !== cpu.cores.length) {
      container.innerHTML = coresMarkup(cpu.cores)
      return
    }
    // Mismo motivo que en los bloques de uptime: actualizar en su lugar
    // conserva los tooltips que creo Tabler al cargar la pagina.
    cpu.cores.forEach(function (value, index) {
      var core = cores[index]
      var bar = core.querySelector('.monitoring-core-bar')
      if (bar) {
        replaceColorClasses(bar, 'bg-', coreColor(value))
        bar.style.height = Math.max(0, Math.min(100, Number(value) || 0)) + '%'
      }
      core.setAttribute('data-bs-original-title', coreTitle(value, index))
    })
  }

  // Graficos interactivos (ApexCharts, el que usa Tabler en su demo). Se crean
  // una vez con la serie que publica el servidor como JSON y despues solo se
  // actualizan con `updateSeries`, para no destruir el chart en cada refresco.
  var charts = {}

  function chartSeries(id) {
    var node = document.getElementById(id)
    if (!node) return null
    try {
      var data = JSON.parse(node.textContent)
      return Array.isArray(data) ? data : null
    } catch (error) {
      return null
    }
  }

  function chartLabels(series) {
    return series.map(function (point) {
      return point.time
    })
  }

  function chartValues(series) {
    return series.map(function (point) {
      return Number(point.count) || 0
    })
  }

  // `requests_per_minute` ya calcula avg_ms por minuto: los minutos sin
  // peticiones no tienen latencia y se dejan como hueco, no como cero.
  function chartLatency(series) {
    return series.map(function (point) {
      if (point.avg_ms === null || point.avg_ms === undefined) return null
      return Number(point.avg_ms) || 0
    })
  }

  function initChart(key, elementId, seriesId, name, noun, withLatency) {
    if (!window.ApexCharts) return
    var element = document.getElementById(elementId)
    var series = chartSeries(seriesId)
    if (!element || !series) return
    var theme = document.documentElement.getAttribute('data-bs-theme') || 'light'
    var options = {
      chart: {
        type: 'area',
        height: 150,
        fontFamily: 'inherit',
        parentHeightOffset: 0,
        toolbar: { show: false },
        zoom: { enabled: false },
        animations: { enabled: false }
      },
      series: [{ name: name, data: chartValues(series) }],
      stroke: { curve: 'smooth', width: 2, lineCap: 'round' },
      fill: {
        type: 'gradient',
        gradient: { shadeIntensity: 1, opacityFrom: 0.35, opacityTo: 0.02, stops: [0, 100] }
      },
      colors: ['var(--tblr-primary)'],
      dataLabels: { enabled: false },
      markers: { size: 0, strokeWidth: 0, hover: { size: 4 } },
      grid: {
        strokeDashArray: 4,
        borderColor: 'var(--tblr-border-color)',
        padding: { top: -8, right: 8, left: 4, bottom: 0 }
      },
      xaxis: {
        categories: chartLabels(series),
        labels: { show: false },
        axisBorder: { show: false },
        axisTicks: { show: false },
        tooltip: { enabled: false }
      },
      yaxis: {
        min: 0,
        forceNiceScale: true,
        labels: {
          style: { colors: 'var(--tblr-body-color)', fontSize: '11px', fontFamily: 'inherit' },
          formatter: function (value) {
            return Math.round(value)
          }
        }
      },
      tooltip: {
        theme: theme,
        shared: Boolean(withLatency),
        intersect: false,
        fillSeriesColor: false,
        title: {
          show: true,
          formatter: function (value, opts) {
            // ApexCharts v5 guarda las categorías en `w.globals.labels`.
            var time = opts.w.globals.labels[opts.dataPointIndex]
            return time || ''
          }
        },
        y: {
          title: {
            formatter: function (opts) {
              // Ocultamos "Serie 1:" que ApexCharts v5 pone por defecto.
              return ''
            }
          },
          formatter: function (value, opts) {
            if (withLatency && opts && opts.seriesIndex === 1) {
              return value === null || value === undefined ? EMPTY : Math.round(value) + ' ms'
            }
            return value + ' ' + (value === 1 ? noun : noun + 's')
          }
        }
      }
    }
    if (withLatency) {
      options.series.push({ name: 'Latencia media', data: chartLatency(series) })
      options.colors.push('var(--tblr-warning)')
      options.stroke = { curve: 'smooth', width: [2, 2], dashArray: [0, 4], lineCap: 'round' }
      options.legend = {
        show: true,
        position: 'top',
        horizontalAlign: 'right',
        fontSize: '11px',
        // Sin esto ApexCharts cae en chart.foreColor (gris oscuro), ilegible
        // con el tema oscuro de Tabler. La variable sigue el cambio de tema.
        labels: { colors: 'var(--tblr-body-color)' },
        markers: { width: 8, height: 8 }
      }
      options.yaxis = [
        options.yaxis,
        {
          min: 0,
          opposite: true,
          forceNiceScale: true,
          labels: {
            style: { colors: 'var(--tblr-body-color)', fontSize: '11px', fontFamily: 'inherit' },
            formatter: function (value) {
              return Math.round(value) + ' ms'
            }
          }
        }
      ]
    }
    var chart = new window.ApexCharts(element, options)
    chart.render()
    charts[key] = chart
  }

  function initCharts() {
    initChart(
      'http',
      'monitoringHttpChart',
      'monitoring-http-series',
      'Peticiones',
      'petición',
      true
    )
    initChart(
      'traffic',
      'monitoringTrafficChart',
      'monitoring-traffic-series',
      'Páginas vistas',
      'página vista'
    )
  }

  function updateChart(key, series, withLatency) {
    var chart = charts[key]
    if (!chart || !Array.isArray(series)) return
    chart.updateOptions({ xaxis: { categories: chartLabels(series) } }, false, false)
    var current = chart.w && chart.w.config && chart.w.config.series
    var updated = [
      { name: current && current[0] ? current[0].name : null, data: chartValues(series) }
    ]
    if (withLatency) {
      updated.push({ name: 'Latencia media', data: chartLatency(series) })
    }
    chart.updateSeries(updated, false)
  }

  function renderRows(tbody, rows) {
    var table = tbody.closest('table')
    var columns = table ? table.querySelectorAll('thead th').length : rows[0].length
    tbody.innerHTML = ''
    if (rows.length === 0) {
      var emptyRow = document.createElement('tr')
      var emptyCell = document.createElement('td')
      emptyCell.colSpan = columns || 1
      emptyCell.className = 'text-secondary'
      emptyCell.textContent = 'Sin datos todav\u00eda.'
      emptyRow.setAttribute('data-empty-row', '')
      emptyRow.appendChild(emptyCell)
      tbody.appendChild(emptyRow)
      return
    }
    rows.forEach(function (cells) {
      var row = document.createElement('tr')
      cells.forEach(function (value, index) {
        var cell = document.createElement('td')
        if (index > 0) cell.className = 'text-end'
        cell.textContent = value === null || value === undefined ? EMPTY : String(value)
        row.appendChild(cell)
      })
      tbody.appendChild(row)
    })
  }

  // Dispositivos y navegadores llevan una barra de distribución. `renderRows`
  // reconstruye el tbody con textContent y se llevaría la barra del template
  // por delante en el primer refresco, así que estos dos tienen renderer propio.
  function renderShareRows(tbody, rows, total) {
    if (!tbody) return
    tbody.innerHTML = ''
    if (rows.length === 0) {
      var emptyRow = document.createElement('tr')
      var emptyCell = document.createElement('td')
      emptyCell.colSpan = 2
      emptyCell.className = 'text-secondary'
      emptyCell.textContent = 'Sin datos todav\u00eda.'
      emptyRow.setAttribute('data-empty-row', '')
      emptyRow.appendChild(emptyCell)
      tbody.appendChild(emptyRow)
      return
    }
    rows.forEach(function (row) {
      var tr = document.createElement('tr')
      var labelCell = document.createElement('td')
      var label = document.createElement('div')
      label.textContent = row.label
      var bar = document.createElement('div')
      bar.className = 'progress progress-sm monitoring-share-bar mt-1'
      bar.setAttribute('aria-hidden', 'true')
      var fill = document.createElement('div')
      fill.className = 'progress-bar'
      fill.style.width = (total > 0 ? (100 * (Number(row.count) || 0)) / total : 0) + '%'
      bar.appendChild(fill)
      labelCell.appendChild(label)
      labelCell.appendChild(bar)

      var countCell = document.createElement('td')
      countCell.className = 'text-end align-top'
      countCell.textContent = row.count === null || row.count === undefined ? EMPTY : String(row.count)

      tr.appendChild(labelCell)
      tr.appendChild(countCell)
      tbody.appendChild(tr)
    })
  }

  // Paginación en cliente de las tablas con `data-paginate="N"`. Las filas se
  // renderizan todas y se muestra una página; la página elegida se guarda en
  // el propio `tbody` para que el refresco no devuelva al usuario a la primera.
  function pageSize(tbody) {
    return parseInt(tbody.getAttribute('data-paginate'), 10) || 0
  }

  function tableRows(tbody) {
    return tbody.querySelectorAll('tr:not([data-empty-row]):not([data-filler-row])')
  }

  function pageCount(tbody) {
    var size = pageSize(tbody)
    if (!size) return 1
    return Math.max(1, Math.ceil(tableRows(tbody).length / size))
  }

  function currentPage(tbody) {
    var page = parseInt(tbody.getAttribute('data-page'), 10) || 1
    return Math.min(Math.max(1, page), pageCount(tbody))
  }

  function applyPage(tbody) {
    var size = pageSize(tbody)
    if (!size) return
    var page = currentPage(tbody)
    var total = pageCount(tbody)
    tbody.setAttribute('data-page', String(page))
    // Las filas de relleno se recalculan en cada página: la última puede traer
    // menos de `size` filas y el card no debe encogerse al cambiar de página.
    tbody.querySelectorAll('[data-filler-row]').forEach(function (row) {
      row.remove()
    })
    var visible = 0
    tableRows(tbody).forEach(function (row, index) {
      var onPage = Math.floor(index / size) + 1 === page
      row.classList.toggle('d-none', !onPage)
      if (onPage) visible += 1
    })
    if (tbody.querySelector('[data-empty-row]')) visible += 1
    var table = tbody.closest('table')
    var columns = table ? table.querySelectorAll('thead th').length : 2
    for (var index = visible; index < size; index += 1) {
      var filler = document.createElement('tr')
      filler.setAttribute('data-filler-row', '')
      filler.className = 'invisible'
      var cell = document.createElement('td')
      cell.colSpan = columns || 1
      cell.textContent = '\u00a0'
      filler.appendChild(cell)
      tbody.appendChild(filler)
    }
    var paginator = document.querySelector(
      '[data-paginator-for="' + tbody.getAttribute('data-table') + '"]'
    )
    if (!paginator) return
    // `invisible` en vez de `d-none`: el paginador conserva su alto aunque no
    // haya más de una página, así el card mantiene el tamaño.
    paginator.classList.toggle('invisible', total <= 1)
    var label = paginator.querySelector('[data-page-label]')
    if (label) label.textContent = page + ' / ' + total
    var prev = paginator.querySelector('[data-page-prev]')
    var next = paginator.querySelector('[data-page-next]')
    if (prev) prev.disabled = page <= 1
    if (next) next.disabled = page >= total
  }

  function bindPaginators() {
    document.querySelectorAll('[data-paginator-for]').forEach(function (paginator) {
      var tbody = document.querySelector(
        '[data-table="' + paginator.getAttribute('data-paginator-for') + '"]'
      )
      if (!tbody) return
      var prev = paginator.querySelector('[data-page-prev]')
      var next = paginator.querySelector('[data-page-next]')
      if (prev) {
        prev.addEventListener('click', function () {
          tbody.setAttribute('data-page', String(currentPage(tbody) - 1))
          applyPage(tbody)
        })
      }
      if (next) {
        next.addEventListener('click', function () {
          tbody.setAttribute('data-page', String(currentPage(tbody) + 1))
          applyPage(tbody)
        })
      }
      applyPage(tbody)
    })
  }

  function applyTables(snapshot) {
    var traffic = snapshot.traffic || {}
    var tables = {
      top_pages: (traffic.top_pages || []).map(function (row) {
        return [row.path, row.views]
      }),
      referrers: ((traffic.referrers || {}).hosts || []).map(function (row) {
        return [row.label, row.count]
      }),
      errors: ((snapshot.errors || {}).items || []).map(function (row) {
        return [row.at, row.message, row.path]
      })
    }
    Object.keys(tables).forEach(function (name) {
      var tbody = document.querySelector('[data-table="' + name + '"]')
      if (!tbody) return
      renderRows(tbody, tables[name])
      applyPage(tbody)
    })

    var pageviews = Number(traffic.pageviews_30m) || 0
    renderShareRows(
      document.querySelector('[data-table="devices"]'),
      traffic.devices || [],
      pageviews
    )
    renderShareRows(
      document.querySelector('[data-table="browsers"]'),
      (traffic.browsers || []).map(function (row) {
        return { label: row.browser, count: row.count }
      }),
      pageviews
    )

    var empty = document.querySelector('[data-traffic-empty]')
    if (empty) empty.classList.toggle('d-none', Boolean(traffic.has_data))
  }

  function applyVitals(snapshot) {
    var metrics = (snapshot.vitals || {}).metrics
    if (!metrics) return
    Object.keys(metrics).forEach(function (key) {
      var block = document.querySelector('[data-vital-metric="' + key + '"]')
      var metric = metrics[key]
      if (!block || !metric) return

      var badge = block.querySelector('[data-vital-badge]')
      if (badge) {
        setBadge(badge, STATE_COLORS[metric.rating] || 'secondary')
        badge.textContent = metric.rating_label || 'sin datos'
      }

      var distribution = metric.distribution || {}
      var samples = metric.samples || 0
      ;['good', 'needs_improvement', 'poor'].forEach(function (rating) {
        var bar = block.querySelector('[data-vital-bar="' + rating + '"]')
        if (!bar) return
        var share = samples ? (100 * (distribution[rating] || 0)) / samples : 0
        bar.style.width = share + '%'
      })
    })
  }

  function applyConnection(ok) {
    var element = document.querySelector('[data-connection-error]')
    if (element) element.classList.toggle('d-none', ok)
  }

  function apply(snapshot) {
    applyValues(snapshot)
    applyStatus(snapshot)
    applyDependencies(snapshot)
    applyUptimeSlots(snapshot)
    applyCores(snapshot)
    applyVitals(snapshot)
    applyTables(snapshot)
    if (snapshot.http && snapshot.http.series) {
      updateChart('http', snapshot.http.series, true)
    }
    if (snapshot.traffic && snapshot.traffic.series) {
      updateChart('traffic', snapshot.traffic.series)
    }
  }

  function refresh() {
    if (inFlight) return Promise.resolve()
    inFlight = true
    return fetch(endpoint, {
      headers: { Accept: 'application/json' },
      credentials: 'same-origin'
    })
      .then(function (response) {
        if (!response.ok) throw new Error('HTTP ' + response.status)
        return response.json()
      })
      .then(function (snapshot) {
        apply(snapshot)
        applyConnection(true)
      })
      .catch(function () {
        // El panel no se vacía por un refresco fallido: se marca la pérdida de
        // conexión y se conserva la última foto buena.
        applyConnection(false)
      })
      .then(function () {
        inFlight = false
      })
  }

  function stop() {
    if (timer !== null) {
      window.clearInterval(timer)
      timer = null
    }
  }

  function start() {
    stop()
    if (paused || document.hidden) return
    timer = window.setInterval(refresh, interval)
  }

  function setPaused(next) {
    paused = next
    if (!toggleButton) return
    toggleButton.querySelector('i').className = paused
      ? 'icon ti ti-player-play me-1'
      : 'icon ti ti-player-pause me-1'
    var label = toggleButton.querySelector('[data-toggle-label]')
    if (label) label.textContent = paused ? 'Reanudar' : 'Pausar'
    if (paused) {
      stop()
    } else {
      refresh()
      start()
    }
  }

  if (toggleButton) {
    toggleButton.addEventListener('click', function () {
      setPaused(!paused)
    })
  }

  if (refreshButton) {
    refreshButton.addEventListener('click', function () {
      refresh()
    })
  }

  // Rueda del mouse sobre el tracking: mueve el scroll lateral del card,
  // no la pagina. `passive: false` porque hay que bloquear el scroll
  // vertical del body con preventDefault.
  function bindTrackingWheel() {
    var wrapper = document.querySelector('.tracking-scroll-wrapper')
    if (!wrapper) return
    wrapper.addEventListener('wheel', function (event) {
      var horizontal = event.deltaX !== 0
      var atEnd =
        wrapper.scrollLeft + wrapper.clientWidth >= wrapper.scrollWidth - 1
      var atStart = wrapper.scrollLeft <= 0
      // Solo captura la rueda vertical cuando hay recorrido en esa
      // direccion; si no, la pagina se sigue scrolleando con normalidad.
      if (!horizontal && ((event.deltaY > 0 && !atEnd) || (event.deltaY < 0 && !atStart))) {
        event.preventDefault()
        wrapper.scrollLeft += event.deltaY
      }
    }, { passive: false })
  }

  function bindOnce() {
    if (bindOnce.done) return
    bindOnce.done = true
    bindTrackingWheel()
    bindPaginators()
    initCharts()
  }
  // Los tooltips de bloques y núcleos los inicializa tabler.min.js (script
  // `defer`) sobre cada [data-bs-toggle="tooltip"], así que acá solo queda el
  // scroll lateral. Se espera `load` para no competir con esos `defer`.
  window.addEventListener('load', bindOnce)

  document.addEventListener('visibilitychange', function () {
    if (document.hidden) {
      stop()
    } else if (!paused) {
      refresh()
      start()
    }
  })

  initStatusAlert()
  start()
})()
