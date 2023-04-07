/* eslint-disable semi */
/* eslint-disable quotes */
/* eslint-disable no-unused-vars */
/* global d3, topojson, echarts */
/**
 * key,val
 * key1,val1
 * key2,val2
 * ...
 *
 * [
 * {key: "key1", val: "val1"},
 * {key: "key2", val: "val2"},
 * ...
 * ]
 */
function readCsvData(csvData) {
  var ret = [];
  var lines = csvData.split('\n');
  var readLine = function(line) { return line.split(','); };
  var captions = readLine(lines[0]);
  for (var i = 1; i < lines.length; i++) {
    if (!lines[i])
      continue;
    var values = readLine(lines[i]);
    var record = {};
    for (var j = 0; j < captions.length; j++) {
      record[captions[j]] = values[j];
    }
    ret.push(record);
  }
  return ret;
}
/** "#E7413C" => [231, 65, 60] */
var hex2Rgb = function(hex) { return (function(n) { return [1, 2, 3].map(function(c) { return n << (c * 8) >>> 24; }); })(Number(hex.replace('#', '0x'))); };
var getElementCssProperty = function(elt, key) { return getComputedStyle(elt).getPropertyValue(key); };
//
var chartMap = {};
function drawEchart(elementId, options) {
  if (chartMap[elementId])
    chartMap[elementId].dispose();
  chartMap[elementId] = echarts.init(document.getElementById(elementId));
  chartMap[elementId].setOption(options);
}
function drawGaugeChart(elementId, data, colorKeys, extraOptions) {
  if (colorKeys === void 0) { colorKeys = ['#2ED47A', '#FEC400']; }
  if (extraOptions === void 0) { extraOptions = {}; }
  var $el = document.getElementById(elementId);
  if (!$el)
    return;
  var colors = colorKeys.map(function(key) {
    if (key.startsWith('--'))
      return getElementCssProperty($el, key);
    return key;
  });
  var options = {
    tooltip: {
      trigger: 'item'
    },
    series: [
      {
        startAngle: 180,
        endAngle: 360,
        type: 'pie',
        radius: ['50%', '90%'],
        avoidLabelOverlap: false,
        label: {
          show: false,
        },
        emphasis: {},
        labelLine: {
          show: false
        },
        data: data.map(function(value, i) { return ({
          name: value[0],
          value: value[1],
          itemStyle: {
            color: colors[i],
          },
        }); }).concat(data.map(function(value) { return ({
          value: data.reduce(function(r, value) { return r + value[1]; }, 0) / (data.length || 1),
          name: null,
          itemStyle: { opacity: 0 },
          tooltip: { show: false },
        }); })),
      }
    ],
  };
  drawEchart(elementId, Object.assign(options, extraOptions));
}
function drawPieChart(elementId, data, colorKeys, extraOptions) {
  if (colorKeys === void 0) { colorKeys = ['#2ED47A', '#FEC400']; }
  if (extraOptions === void 0) { extraOptions = {}; }
  var $el = document.getElementById(elementId);
  if (!$el)
    return;
  var colors = colorKeys.map(function(key) {
    if (key.startsWith('--'))
      return getElementCssProperty($el, key);
    return key;
  });
  var options = {
    tooltip: {
      trigger: 'item'
    },
    series: [
      {
        startAngle: 180,
        endAngle: 360,
        type: 'pie',
        radius: ['75%', '90%'],
        avoidLabelOverlap: false,
        label: {
          show: false,
        },
        emphasis: {},
        labelLine: {
          show: false
        },
        data: data.map(function(value, i) { return ({
          name: value[0],
          value: value[1],
          itemStyle: {
            color: colors[i],
          },
        }); })
      }
    ],
  };
  drawEchart(elementId, Object.assign(options, extraOptions));
}
function sampleByCount(datas, count) {
  if (datas.length <= count)
    return datas;
  var interval = datas.length / count | 0;
  return datas.filter(function(data, i) { return i % interval === 0; });
}

function drawLineChart(elementId, csvData, colorKey, languageCode, extraOptions) {
  if (colorKey === void 0) { colorKey = '#E7413C'; }
  if (extraOptions === void 0) { extraOptions = {}; }
  var $el = document.getElementById(elementId);
  if (!$el)
    return;
  var color = colorKey.startsWith('--') ? getElementCssProperty($el, colorKey) : colorKey;
  var data = sampleByCount(readCsvData(csvData), 100);
  var values = data.map(function(value) { return [value.date, parseFloat(value.value)]; });
  var options = {
    xAxis: {
      type: 'category',
      data: values.map(function(value) { return value[0]; }),
      axisLine: {
        show: false,
      },
      axisTick: {
        show: false,
      },
    },
    yAxis: {
      type: 'value',
      splitLine: {
        lineStyle: {
          type: 'dashed',
          color: '#D3D8DD',
        },
      },
      axisLabel: {
        formatter: function (value, index) {
          var formatter = new Intl.NumberFormat(languageCode)
          return formatter.format(value)
        }
      }
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(25, 42, 62, 0.8)',
      borderWidth: 0,
      textStyle: {
        color: '#fff',
        lineHeight: 14,
      },
      padding: [5, 20],
      borderRadius: 100,
      axisPointer: {
        type: 'none',
      },
      snap: false,
      formatter: function(params) {
        return String(params[0].name) + '<br />' + String(params[0].data);
      },
    },
    series: [{
      data: values.map(function(value) { return value[1]; }),
      type: 'line',
      smooth: true,
      symbol: 'emptyCircle',
      showSymbol: false,
      sampling: 'average',
      itemStyle: {
        color: "rgba(" + hex2Rgb(color).join(',') + ", 0.8)",
      },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{
          offset: 0,
          color: "rgba(" + hex2Rgb(color).join(',') + ", 0.8)"
        }, {
          offset: 1,
          color: "rgba(" + hex2Rgb(color).join(',') + ", 0)"
        }])
      },
    }],
    grid: {
      top: 20,
      right: 30,
      bottom: 40,
      left: 55,
    },
  };
  if (Reflect.apply(Object.prototype.toString, extraOptions, []) === '[object Function]') {
    extraOptions = extraOptions(values);
  }
  drawEchart(elementId, Object.assign(options, extraOptions));
}

function drawSimplifiedChart(elementId, csvData, colorKey, extraOptions) {
  if (colorKey === void 0) { colorKey = '#7ab9f3'; }
  if (extraOptions === void 0) { extraOptions = {}; }
  var $el = document.getElementById(elementId);
  if (!$el)
    return;
  var color = colorKey.startsWith('--') ? getElementCssProperty($el, colorKey) : colorKey;
  var data = sampleByCount(readCsvData(csvData), 100);
  var values = data.map(function(value) { return [value.date, parseFloat(value.value)]; });
  var options = {
    xAxis: {
      type: 'category',
      data: values.map(function (value) {return value[0]}),
      axisLine: {
          show: false,
      },
      axisTick: {
          show: false,
      },
      axisLabel: {
          show: false
      },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
          show: false
      },
      splitLine: {
          show: false
      },
    },
    tooltip: {},
    series: [{
      data: values.map(function(value) { return value[1]; }),
      type: 'line',
      smooth: true,
      symbol: 'emptyCircle',
      showSymbol: false,
      sampling: 'average',
      silent: true,
      itemStyle: {
        color: "rgba(" + hex2Rgb(color).join(',') + ", 0.8)",
      },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{
          offset: 0,
          color: "rgba(" + hex2Rgb(color).join(',') + ", 0.8)"
        }, {
          offset: 1,
          color: "rgba(" + hex2Rgb(color).join(',') + ", 0)"
        }])
      },
    }],
    grid: {
      top: 0,
      right: 0,
      bottom: 0,
      left: 0,
    }
  }
  if (Reflect.apply(Object.prototype.toString, extraOptions, []) === '[object Function]') {
    extraOptions = extraOptions(values);
  }
  drawEchart(elementId, Object.assign(options, extraOptions));
}

function readCsvDataTrending(csvData) {
  var records = readCsvData(csvData).reverse()
  var latestValue = records[0].value
  for (var i = 1; i < records.length; i++) {
    var value = records[i].value
    if (value > latestValue) return -1
    if (value < latestValue) return 1
  }

  return 0
}

function lightTrendingMark(selector, csvData) {
  var $el = document.querySelector(selector)
  if ($el) {
    var trending = readCsvDataTrending(csvData)
    if (trending > 0) {
      $el.classList.add('fa-long-arrow-up')
      $el.classList.add('analytics-widget__caption-mark--up')
    } else if (trending < 0) {
      $el.classList.add('fa-long-arrow-down')
      $el.classList.add('analytics-widget__caption-mark--down')
    }
  }
}

function drawMap(elementId, csvData, mapJsonFile) {
  var containerEl = document.getElementById(elementId),
    width = containerEl.clientWidth,
    height = width * 0.6,
    container = d3.select(containerEl),
    svg = container.select('svg')
        .attr('viewBox', '0 0 '+ width +' ' + height)
        .attr('width', '100%')
        .attr('height', '100%');

  var values = d3.map();

  const scaleFactor = containerEl.clientWidth / 768, scaleDefault=170;
  scaleRatio = scaleFactor > 0 ? scaleFactor * scaleDefault : scaleDefault;
  var projection = d3.geoNaturalEarth1()
      .scale(scaleRatio)
      .translate([width / 2, height / 2*1.1])
      .precision(.1);
  var path = d3.geoPath(projection);

  var max_value = 0;
  var data = d3.csvParse(csvData, function(d) {
    values.set(d.id, [d.label, +d.value]);
    if (+d.value > max_value) {
      max_value = d.value;
    }
  });

  var color = d3.scaleLinear()
      .domain([1, max_value])
      .range([0.1, 1]);

  //d3.json("https://d3js.org/world-110m.v1.json", function(error, world) {
  d3.json(mapJsonFile, function(error, world) {
    if (error) throw error;

    svg.append("g")
        .attr("class", "map--country-borders")
      .selectAll("path")
      .data(topojson.feature(world, world.objects.countries).features)
      .enter().append("path")
        .attr("d", path);

    svg.append("g")
      .selectAll("path")
      .data(topojson.feature(world, world.objects.countries).features)
      .enter().append("path")
        .attr("class", function(d) {
          if (values.get(d.id)) {
            return "map--country-color";
          }
          return "map--country-blank";
        })
        .attr("stroke", "none")
        .attr("opacity", function(d) {
          var value = values.get(d.id)
          if (value) {
            return color(value[1]);
          }
          return 1;
        })
        .attr("d", path)
      .append("title")
        .text(function(d) {
          var value = values.get(d.id)
          if (value) {
            return value[0] + "\n" + value[1];
          }
          return;
        });

    svg.append("path")
        .datum(topojson.mesh(world, world.objects.countries, function(a, b) { return a !== b; }))
        .attr("class", "map--country-borders")
        .attr("d", path);
  });
}
