export const OUTDOOR_SHELL_COLORS = {
  A: '进口云彩白',
  B: '进口云彩黑',
  C: '进口天蓝',
  D: '进口云彩蓝',
  E: '进口午夜黑',
  F: '进口古铜',
  G: '进口珍珠灰',
  H: '进口云灰',
  I: '进口珍珠白',
  J: '进口石膏白',
  K: '国产云彩白',
  L: '国产云彩黑',
  M: '国产全白',
  N: '进口日落色',
  O: '三菱国产白',
  P: '进口芝麻绿',
  Q: '内缸黑色+外缸白色',
  R: '内缸白色+外缸黑色',
  S: '进口烟雾灰',
  T: '进口海洋蓝'
}

export const OUTDOOR_HOLE_CODES = {
  '1': '无喷嘴',
  '2': '标准孔',
  '3': '标准孔+',
  '4': '孔位4',
  '5': '孔位5',
  '6': '孔位6'
}

export const OUTDOOR_COLOR_HOLE_CODES = (() => {
  const result = {}
  Object.entries(OUTDOOR_SHELL_COLORS).forEach(([colorCode, colorName]) => {
    Object.entries(OUTDOOR_HOLE_CODES).forEach(([holeCode, holeName]) => {
      result[`${colorCode}${holeCode}`] = `${colorName}+${holeName}`
    })
  })
  return result
})()

export const OUTDOOR_NOZZLE_CODES = {
  '00': '无喷嘴',
  '1A': '眉毛水喷（标准）',
  '1B': '眉毛水喷+气喷（标准）',
  '1C': '眉毛气泡改水喷',
  '1D': '眉毛座位处气泡改水喷',
  '1E': '眉毛气喷改无气水喷',
  '1F': '眉毛水喷带灯',
  '1H': '眉毛增加水喷',
  '1I': '眉毛水喷带灯+气喷改无气水喷',
  '1J': '特殊配置',
  '1K': '眉毛喷嘴趟位气泡改水喷+气喷',
  '1L': '眉毛水喷增加瀑布',
  '1M': '眉毛减少水喷（不带气喷）',
  '1N': '额外增加水喷（不带气喷）',
  '1O': '眉毛部分喷嘴带灯+节拍器',
  '1P': '眉毛气改水+河喷',
  '1Q': '眉毛水喷（加拿大简配Alpine)',
  '1R': '眉毛水喷（加拿大豪配Alpine)',
  '1S': '眉毛增加水喷（带气喷）',
  '1T': '眉毛水喷带灯+瀑布',
  '1U': '眉毛水喷带灯+气喷',
  '1V': '眉毛气喷改1寸水喷（串联气泵）',
  '1W': '眉毛部分喷嘴带灯',
  '1Z': '眉毛水喷+3个河喷',
  '13': '眉毛带多孔喷带灯',
  '2A': '猫眼水喷（标准）',
  '2B': '猫眼水喷+气喷（标准）',
  '2E': '猫眼气喷改无气水喷(瑞典）',
  '2G': '猫眼气喷改无气水喷',
  '2J': '猫眼气喷改无气水喷',
  '2O': '猫眼部分喷嘴带灯+节拍器',
  '2V': '猫眼气喷改1寸水喷（串联气泵）',
  '2W': '猫眼部分喷嘴带灯',
  '3A': '西默水喷（标准）',
  '3M': '西默减少水喷（不带气喷）',
  '3E': '腾龙大地深灰（瑞典）',
  '4A': 'LVJ标准水喷',
  '4E': '腾龙大地浅灰（瑞典）',
  '5A': '钻石标准水喷',
  '5B': '钻石标准水喷+气喷',
  '51': '灰色钻石旋转喷/标准数量',
  '52': '全包不锈钢钻石旋转喷/标准数量',
  AI: '钻石扁平深灰带灯+气改无气',
  BI: '钻石扁平浅灰带灯+气改无气',
  BW: '钻石扁平浅灰部分喷嘴带灯',
  '6A': '光环水喷（标配）',
  '7A': '贝特标准水喷',
  '7H': '贝特增加水喷',
  '8A': '光边光面标准水喷',
  '8C': '光边光面气泡改1寸水喷',
  '8W': '光边光面部分喷嘴带灯',
  '9A': '眉毛水喷带清扫喷嘴',
  '9E': '眉毛带灯气喷改无气水喷带清扫喷嘴',
  '9I': '眉毛部分喷嘴带灯气喷改1寸水喷带清扫喷嘴'
}

export const OUTDOOR_POWER_CODES = {
  '0': '无电源标准',
  A: '220-240V/50Hz',
  B: '双110V/60Hz',
  C: '220-240V/50Hz英插',
  D: '220-240V/50Hz澳插',
  E: '220-240V/50Hz欧插（16A）',
  F: '380V/50HZ',
  G: '220-240V/50Hz澳插（10A）',
  H: '单110V/60Hz美插（配漏保转换器）',
  I: '单110V/60Hz美插带漏保',
  J: '220V/60Hz',
  K: '220/50Hz国插带漏保（16A）',
  L: '220-240V/50Hz英插（电源线长5米）',
  N: '单110V/60Hz'
}

export const OUTDOOR_CONTROL_CODES = {
  '00': '无控制器',
  '11': 'YE-5+K1000+3KW(带热泵功能）',
  '15': 'YJ-3+K1000+3KW',
  '16': 'YJ-3+K300+4KW（1个泵）',
  '17': 'YJ-2+K506+4KW',
  '18': 'YE-5+K806+3.6KW（带485热泵模块）/YJ-2+K300+1.3KW',
  '19': 'YJ-2+K300+4KW',
  '1A': 'YJ-2+K300+2KW',
  '1B': 'YJ-2+K300+3KW',
  '1C': 'YJ-2+K506+3KW',
  '1D': 'YJ-2+K506+2KW',
  '1E': 'YJ-3+K300+2KW（1个泵）',
  '1F': 'YJ-3+K300+3KW（2个泵）',
  '1G': 'YJ-3+K506+3KW',
  '1H': 'YE-5+K506+3KW',
  '1I': 'YE-5+K506+3.6KW',
  '1J': 'YE-5+K806+3KW',
  '1K': 'YE-5+K806+3.6KW',
  '1L': 'YE-5+K1000+3KW',
  '1M': 'YE-5+K1000+3.6KW',
  '1N': 'YJ-3+K300+3KW（1个泵）',
  '1O': 'YJ-3+K506+2KW',
  '1P': 'YJ-3+K506+4KW',
  '1Q': 'YE-3+K300+3KW（2个泵）',
  '1R': 'YE-3+K506+3KW',
  '1S': 'YE-3+K300+3KW（1个泵）',
  '1T': 'YE-3+K506+2KW（带485热泵模块）',
  '1U': 'YE-3+K506+3KW（带485热泵模块）',
  '1Y': 'YJ-3+K300+2KW（2个泵）',
  '2A': 'BP6013 G1+TP600+3KW',
  '2C': 'BP6013 G1+T形触摸面板+3KW',
  '2G': 'BP200+TP500+2KW',
  '2L': 'BP2100 G0+TP700+3KW',
  '2M': 'BP2100 G1+TP700+3KW',
  '2O': 'BP200+TP400+2KW',
  '2P': 'BP601+TP800+3KW',
  '2Q': 'BP601+TP600+3KW',
  '2R': 'BP601+T形触摸面板+3KW',
  '2S': 'BP2100 G0+TP600+3KW',
  '2T': 'BP2100 G0+TP800+3KW',
  '2U': 'BP2100 G0+T型触摸面板+3KW',
  '2V': 'BP2100 G1+方形触摸面板+3KW/BP2100 G0+方形触摸面板+3KW',
  '2W': 'BP2100 G1+TP800+3KW',
  '2X': 'BP2100 G1+T型触摸面板+3KW',
  '31': 'YE-5+Flx.go圆形面板+4KW(美标/配2-3个泵选用)',
  '35': 'YJ-3+K1000+4KW(美标/配1个泵选用)',
  '3A': 'YJ-2+K1000+4KW(美标/配1个泵选用)',
  '3B': 'YJ-2+K300+4KW(美标/配1个泵选用)',
  '3D': 'YJ-2+K506+4KW(美标/配1个泵选用)',
  '3E': 'YE-5-V3FLX+K1000+4KW(美标)',
  '3G': 'YJ-3+K506+4KW(美标/配1个泵选用)',
  '3H': 'YE-5+K506+4KW(美标/配2-3个泵选用)',
  '3J': 'YE-5+K806+4KW(美标/配2-3个泵选用)',
  '3L': 'YE-5+K1000+4KW(美标/配2-3个泵选用)',
  '3N': 'YJ-3+K300+4KW(美标/配1个泵选用)',
  '3P': 'YE-5+K300+4KW(美标)',
  '3Q': 'YJ-2+K806+4KW(美标/配1个泵选用)',
  '3R': 'YE-5+K300+4KW(美标/配2-3个泵选用)',
  '3Y': 'YJ-3+K300+4KW(美标/配2个泵)',
  '4S': 'BP2000+TP600+5.5KW（美标）',
  '4U': 'BP2000+T型触摸面板+5.5KW（美标）',
  '5A': 'P23B32+PB559+3KW',
  '5B': 'P68B123+PB562+4KW（欧标/美标通用/配1水泵/1水泵+1风泵选用/带WIFI功能/面板带贝拉乔商标）',
  '5C': 'P68B123+PB562+3KW（美标配2个水泵选用/欧标配1-2个泵选用/带WIFI功能/面板带贝拉乔商标）',
  '5D': 'P69B133+PB565+4KW（欧标/美标通用/带WIFI功能）',
  '5E': 'P68B123+PB565+4KW（欧标/美标通用/配1水泵/1水泵+1风泵选用/带WIFI功能）',
  '5F': 'P69B133+PB565+3KW（欧标/美标通用/带WIFI功能）',
  '5G': 'P68B123+PB563+3KW（美标配2个水泵选用/欧标配1-2个泵选用）',
  '5H': 'P69B133+PB563+4KW（美标）',
  '5I': 'P68B123+PB562+4KW（美标/配1水泵/1水泵+1风泵选用/带WIFI功能/面板带Joyonway商标）',
  '5J': 'P68B123+PB562+3KW（美标配2个水泵选用/欧标配1-2个泵选用/带WIFI功能/面板带Joyonway商标）',
  '5K': 'P69B133+PB563+4KW（美标/面板带Joyonway商标）',
  '5L': 'P68B123+PB565+2KW（欧标/美标通用/带WIFI功能）',
  '5M': 'P68B123+PB562+2KW（带WIFI功能/面板带贝拉乔商标）',
  '5N': 'P68B123+PB562+4KW（带WIFI功能/贝拉乔灰白面板贴纸）',
  '5O': 'P68B123+PB563+4KW（贝拉乔灰白面板贴纸）',
  '5X': 'P25B85+PB554+2KW',
  '5Y': 'P23B32+PB554+3KW',
  '6Z': '控制盒带欧插+触摸开关（冰岛）',
  T: 'BP2100 G0+TP800+3KW'
}

export const OUTDOOR_WATER_PUMP_CODES = {
  '00': '无水泵',
  '11': '1个循环LX+2个双速3HPLX',
  '12': '2个双速3HPLX+1个单速1HP',
  '15': '1个循环LX+1个单速3HPLX+1个单速1HP',
  '16': '1个循环LX+2个单速3HPLX+1个单速1HP',
  '1C': '1个LX循环系统',
  '1D': '1个循环gecko+1个单速3HPLX',
  '1E': '1个循环gecko+1个单速2.5HPLX',
  '1F': '1个循环LX+1个单速2HPLX+1个单速2.5HPLX',
  '1G': '1个循环LX+1个单速2.5HPLX',
  '1H': '1个循环LX+1个单速3HPLX',
  '1I': '1个循环gecko+2个单速2.5HPLX',
  '1J': '1个循环gecko+2个单速3HPLX',
  '1K': '1个循环Gecko+2个单速3HPGecko',
  '1L': '1个循环gecko+1个单速3HPgecko',
  '1M': '1个循环LX+1个单速2HPLX+1个单速3HPLX',
  '1N': '1个循环LX+2个单速2HPLX',
  '1O': '1个循环LX+2个单速3HPLX+1个单速2HPLX',
  '1P': '1个循环LX+2个单速3HPLX',
  '1Q': '1个循环gecko+1个单速3HPgecko+1个1HP单速（配浅灰过滤器）',
  '1R': '1个循环Gecko+3个单速3HPGecko',
  '1S': '1个循环gecko+3个单速3HPLX',
  '1T': '1个循环LX+3个单速3HPLX',
  '1U': '1个循环LX+3个单速3HPLX+1个单速1HP',
  '1V': '1个循环gecko+1个单速3HPgecko+1个1HP单速',
  '1W': '1个循环gecko+2个单速3HPgecko+1个1HP单速',
  '1X': '1个循环gecko+2个单速3HPLX+1个1HP单速',
  '1Y': '1个循环gecko+2个单速3HPgecko+1个1HP单速（配浅灰过滤器）',
  '1Z': '1个循环LX+1个单速3HPLX(过滤器带SPAtec商标)',
  '2B': '1个双速2HPLX（标配）',
  '2D': '2个双速3HPLX',
  '2G': '1个双速2.5HPLX',
  '2H': '1个双速3HPLX',
  '2I': '1个双速2.5HPLX+2个单速3HPLX（标配）',
  '2J': '1个双速2.5HPLX+1个单速3HPLX',
  '2K': '1个双速3HPLX+2个单速3HPLX',
  '2L': '1个双速3HPLX+1个单速3HPLX',
  '2M': '1个双速3HPLX+1个单速1HP（标配）',
  '2N': '1个双速2.5HPLX+1个单速2HPLX',
  '2V': '1个双速2.5HPLX+1个单速1HP（标配）',
  '2W': '1个双速3HPLX+1个单速3HPLX+1个单速1HP（标配）',
  '2Z': '双速泵带特殊过滤器',
  '33': '1个循环Gecko+2个单速3HPGecko+1个1HP单速1HP（美标）',
  '34': '1个循环Gecko+1个单速3HPLX+1个单速1HP（美标）',
  '35': '1个循环LX+1个单速3HPLX+1个单速1HP（美标）',
  '36': '1个循环LX+2个单速3HPLX+1个单速1HP（美标）',
  '37': '1个循环LX+1个单速3HPgecko+1个单速1HP（美标）',
  '38': '1个循环LX+2个单速3HPgecko（美标）',
  '3D': '1个循环gecko+1个单速3HPLX（美标）',
  '3E': '1个循环LX+2个单速3HPLX+1个1.5HP单速（美标）',
  '3F': '1个循环LX+1个单速2HPLX（美标）/1个循环LX+2个单速3HPLX（美标/配浅灰过滤器）',
  '3G': '1个循环gecko+1个单速3HPgecko（美标）',
  '3H': '1个循环LX+1个单速3HPLX（美标）',
  '3J': '1个循环Gecko+2个单速3HPLX（美标）',
  '3K': '1个循环gecko+2个单速3HPgecko（美标）',
  '3M': '1个循环LX+1个双速3HPgecko+1个单速1HP（美标）',
  '3P': '1个循环LX+2个单速3HPLX（美标）',
  '3S': '1个循环Gecko+3个单速3HPLX（美标）',
  '3T': '1个循环LX+3个单速3HPLX（美标）',
  '3U': '1个循环LX+3个单速3HPLX+1个单速1HP（美标）',
  '3W': '1个循环Gecko+2个单速3HPLX+1个单速1HP（美标）',
  '3Y': '1个循环Gecko+3个单速3HPLX+1个单速1HP（美标）',
  '3Z': '1个循环LX+2个单速3HPLX+1个1.5HP单速（美标/配浅灰过滤器）',
  '4A': '1个双速3HPgecko（美标）',
  '4B': '1个双速2HPLX（美标/单110V）',
  '4C': '1个双速1.5HPLX+1个单速3HPLX（美标/配浅灰过滤器）',
  '4D': '2个双速3HPLX（美标）',
  '4E': '1个双速1.5HPLX+1个单速2HPLX（美标/配浅灰过滤器）',
  '4F': '1个双速3HPgecko+1个单速3HPLX（美标）',
  '4H': '1个双速3HPLX（美标）',
  '4I': '1个双速3HPLX+1个单速3HPLX（美标）',
  '4J': '1个双速3HPLX+2个单速3HPLX（美标）',
  '4K': '1个双速3HPgecko+2个单速3HPgecko（美标）',
  '4L': '1个双速3HPgecko+1个单速3HPgecko（美标）',
  '4M': '1个双速3HPLX+1个单速3HPLX+1个单速1HP（美标）',
  '4V': '1个双速3HPgecko+1个1HP单速（美标）',
  '4W': '1个双速3HPgecko+1个单速3HPgecko+1个1HP单速（美标）',
  '4Z': '1个双速2HPLX（美标/单110V/配浅灰过滤器）',
  '5A': '1个单速+1个循环管路（无泵）',
  '5B': '2个单速+1个循环管路（无泵）',
  '5C': '3个单速+1个循环管路（无泵）',
  '6D': '2个双速泵管路',
  '71': '1个循环LX+2个双速3HPGecko（美标）',
  '78': '1个循环LX+1个双速3HPgecko（美标）',
  '7A': '2个双速3HPgecko（美标）',
  '7B': '1个循环gecko+1个双速3HPgecko（美标）',
  '7D': '2个双速3HPgecko+1个单速3HPLX（美标）',
  '7E': '1个双速3HPgecko+1个变频泵gecko（美标）',
  '7F': '2个变频泵gecko（美标）',
  '7G': '1个循环LX+1个双速3HPLX（美标）',
  '7K': '1个循环Gecko+2个双速3HPGecko（美标）',
  '7L': '2个双速3HPgecko+1个单速3HPgecko（美标）',
  '7P': '1个循环LX+2个双速3HPLX（美标）',
  '7W': '2个双速3HPgecko+1个1HP单速（美标）',
  '8B': '1个循环LX+1个单速2HPLX（美标/单110V/双110V通用）'
}

export const OUTDOOR_AIR_PUMP_CODES = {
  '0': '无风泵',
  '1': '1个0.9HP风泵（美标）',
  '2': '1个0.9HP加热风泵+香薰管路（无加热风泵）',
  A: '1个0.9HP风泵',
  B: '1个0.9HP风泵+香薰',
  C: '1个0.9HP加热风泵',
  D: '1个0.9HP加热风泵+香薰',
  E: '1个0.6HP风泵',
  F: '1个0.6HP风泵+香薰',
  G: '1个0.6HP加热风泵',
  H: '1个0.6HP加热风泵+香薰',
  I: '1个0.9HP风泵+腾龙/LVJ香薰',
  J: '1个0.6HP加热风泵+腾龙/LVJ香薰',
  K: '1个0.9HP加热风泵+腾龙/LVJ香薰',
  L: '1个0.4HP风泵'
}

export const OUTDOOR_SANITATION_CODES = {
  '0': '无消毒系统',
  '6': '臭氧（美标/带循环泵用）',
  A: '臭氧',
  B: 'UV',
  C: '臭氧+UV',
  D: '臭氧+盐氯预装管',
  E: 'UV+盐氯预装管',
  F: '臭氧+UV+盐氯预装管',
  G: '臭氧+IN.Clear',
  H: '臭氧（美标）',
  I: '臭氧管路（无臭氧/无射流器/无稳合器）',
  J: 'IN.Clear+臭氧管道（无臭氧/无射流器/无稳合器）',
  K: '臭氧+ClearBlue（美标）',
  M: '臭氧+UV（美标）',
  N: 'UV（美标）',
  O: '臭氧+投药器',
  P: 'UV+IN.Clear',
  Q: '臭氧管路（无臭氧）+UV（美标）',
  R: '臭氧+UV+投药器+臭氧混合器'
}

export const OUTDOOR_MULTIMEDIA_CODES = {
  '0': '无多媒体',
  '1': '带2个共振喇叭底座',
  '2': '带4个共振喇叭+低音炮+gecko-WIFI',
  '3': '普兰简配蓝牙+共振喇叭+Gecko-wifi（澳标wifi）',
  '6': 'gecko蓝牙+裙边喇叭',
  '7': '罗浮简配蓝牙+共振喇叭+Gecko-wifi（美标）',
  '9': '罗浮豪配蓝牙+低音炮（欧标/美标通用）',
  A: 'gecko蓝牙',
  B: 'gecko-WIFI',
  C: 'gecko蓝牙+WIFI',
  D: 'balboa蓝牙',
  E: 'balboa-wifi',
  F: 'balboa蓝牙+wifi',
  G: '普兰简配蓝牙+共振喇叭',
  H: '普兰豪配蓝牙+低音炮（停用）',
  I: '普兰简配蓝牙+缸面喇叭',
  J: '普兰简配蓝牙+共振喇叭+Gecko-wifi',
  K: '普兰简配蓝牙+共振喇叭+Balboa-wifi',
  L: '罗浮豪配蓝牙+低音炮（蓝牙带欧标漏保插头）/罗浮豪配蓝牙+低音炮+Gecko-wifi',
  M: '普兰豪配蓝牙+低音炮+Gecko-wifi（停用）',
  O: '罗浮豪配蓝牙+低音炮+Gecko-wifi（美标）',
  P: 'gecko-WIFI（美标）',
  Q: '罗浮简配蓝牙+共振喇叭（欧标/美标通用）',
  R: 'gecko蓝牙+WIFI（美标）',
  S: '普兰简配蓝牙+共振喇叭（美标）',
  T: '普兰简配蓝牙+共振喇叭+Gecko-wifi（美标）',
  U: '普兰豪配蓝牙+低音炮（美标）',
  V: '方形蓝牙带内置低音炮+共振喇叭/方形蓝牙带内置低音炮+共振喇叭（蓝牙带欧标漏保插头）',
  W: '方形蓝牙带内置低音炮+Gecko-wifi',
  X: '普兰豪配蓝牙+低音炮+Gecko-wifi（美标）',
  Z: 'gecko蓝牙+2个缸面喇叭+WIFI（美标）'
}

export const OUTDOOR_LIGHTING_CODES = {
  '0': '无灯光系统',
  A: '带水底灯',
  B: '水底灯+阀带灯',
  C: '带水底灯+阀带灯+缸边灯',
  D: '带水底灯+阀带灯+缸边灯+转角灯',
  E: '水底灯+阀带灯+缸边灯+贝拉乔logo灯',
  F: '水底灯+阀带灯+转角灯+logo灯',
  G: '带水底灯+阀带灯+缸边灯+转角灯',
  H: '带水底灯+阀带灯+缸边灯+转角灯（瑞典配置）',
  I: '水底灯+阀带灯+缸边灯贝拉乔LOGO灯（YJ/YE-V3版本电控用）',
  J: '带水底灯+阀带灯+缸边灯+转角灯（无灯杯座/增加灯杯座）',
  K: '带水底灯+阀带灯+缸边灯(减少灯杯座/增加灯杯座）',
  L: '带水底灯+阀带灯+缸边灯+转角灯+裙边灯（无灯杯座）',
  M: '带水底灯+阀带灯+缸边灯+转角灯（减少灯杯座）',
  N: '带水底灯+缸边灯+阀带灯（YJ/YE-V3版本电控用）',
  O: '带水底灯+阀带灯+缸边灯+转角灯（YJ/YE-V3版本电控用）',
  P: '带水底灯+阀带灯+缸边灯+转角灯(无灯杯座）（YJ/YE-V3版本电控用）',
  Q: '带水底灯+阀带灯+Logo灯',
  R: '带水底灯+阀带灯+缸边灯(减少灯杯座/增加灯杯座）（YJ/YE-V3版本电控用）',
  S: '带水底灯+阀带灯+缸边灯（池壁灯）+1个灯杯座+转角灯（YJ/YE-V3版本电控用）',
  T: '带水底灯+阀带灯+缸边灯+转角灯+贝拉乔LOGO灯/（YJ/YE-V3版本电控用）',
  U: '带水底灯+阀带灯+缸边灯+转角灯+贝拉乔logo灯',
  V: '水底灯+阀带灯+缸边灯+转角灯带+裙边灯带+贝拉乔logo灯',
  W: '带水底灯+阀带灯+缸边灯+3个灯杯座+转角灯+裙边灯+贝拉乔logo灯（YJ/YE-V3版本电控用）',
  X: '水底灯+阀带灯+缸边灯+3个灯杯座（浅灰）+转角灯带+裙边灯带+贝拉乔logo灯'
}

export const OUTDOOR_BOTTOM_CODES = {
  '0': '无支架',
  A: '单底支架',
  B: '半三明治底支架',
  C: '全三明治底支架',
  D: '单底带快装铝架',
  E: '玻璃纤维/单底支架(加高970)',
  F: '玻璃纤维/半三明治底支架(加高970)/玻璃纤维/单底镀锌支架(产品800高)',
  G: '玻璃纤维/全三明治底支架(800高)',
  H: '玻璃纤维/单底支架(800高)',
  I: '玻璃纤维/单底支架(底部带铝膜)',
  J: '全三明治底支架(配镀锌支架)',
  K: '单底镀锌支架',
  L: '玻璃纤维/316不锈钢支架无底板/单底镀锌支架+铝膜',
  M: '玻璃纤维/单底支架',
  N: '玻璃纤维/半三明治底支架',
  O: '玻璃纤维/全三明治底支架',
  P: '玻璃纤维/全三明治底支架(配镀锌支架)',
  Q: '玻璃纤维/单底镀锌支架'
}

export const OUTDOOR_SIDE_INSULATION_CODES = {
  '0': '无缸侧保温',
  A: '四面保温',
  B: '帘子保温',
  C: '电机面保温板',
  D: '四面保温板（配镀锌支架用）'
}

export const OUTDOOR_BODY_INSULATION_CODES = {
  '0': '无缸体保温',
  A: '户外缸单层发泡',
  B: '满泡',
  C: '满泡+电机面单泡',
  D: '户外缸单层发泡(2cm)'
}

export const OUTDOOR_SKIRT_CODES = {
  '0': '无裙边',
  '1': '单面色/黑橡木网纹铝板聚氨酯裙边（产品高970）',
  A: '灰色生态裙边',
  B: '柚木色生态裙边',
  C: '咖啡色生态裙边',
  D: '灰色覆膜铝蜂窝裙边',
  E: '柚木色覆膜铝蜂窝裙边',
  F: '灰色油漆铝蜂窝裙边',
  G: '铜色油漆铝蜂窝裙边',
  H: '白色油漆铝蜂窝裙边',
  I: '拉丝油漆铝蜂窝裙边',
  J: '单面色/黑橡木网纹钢板聚氨酯裙边（产品800高）',
  K: '灰色覆膜铝蜂窝裙边（产品高800）',
  L: '灰色聚氨酯裙边',
  M: '灰色/铝板贴膜聚氨酯裙边(产品高970)/灰色/铝板/聚氨酯裙边（产品高800）',
  N: '灰色/铝板贴膜聚氨酯裙边',
  O: '双面色/黑橡木网纹铝板聚氨酯裙边',
  P: '棕色/铝板贴膜聚氨酯裙边',
  Q: '灰色/钢板滚涂/聚氨酯裙边',
  R: '灰色/钢板滚涂/聚氨酯裙边（产品高800）',
  S: '实木裙边',
  T: '双面色/灰色+棕色/铝板贴膜聚氨酯裙边',
  U: '棕色/铝板贴膜聚氨酯裙边（产品高970）',
  V: '灰色/PS裙边',
  W: '棕色/PS裙边',
  X: '单面色/黑橡木网纹铝板聚氨酯裙边/黑橡木/PS裙边',
  Y: '单面色/黑橡木网纹钢板聚氨酯裙边',
  Z: '双面色/黑橡木网纹滚涂+棕色贴膜聚氨酯裙边'
}

export const OUTDOOR_CORNER_CODES = {
  '0': '无转角',
  A: '灰色生态转角',
  B: '柚木色生态转角',
  C: '咖啡色生态转角',
  D: '灰色铝转角',
  F: '棕色铝转角',
  G: '铜色铝转角',
  H: '白色铝转角',
  I: '拉丝铝转角',
  J: '塑料转角',
  L: '棕色PS转角',
  M: '灰色PS转角',
  P: '黑橡木PS转角',
  Q: '黑橡木铝转角'
}

export const OUTDOOR_STAIR_CODES = {
  '0': '无台阶',
  A: '灰色二级台阶',
  B: '柚木色二级台阶',
  C: '黑色二级台阶',
  D: '咖啡色二级台阶',
  E: '灰色二级弧形台阶',
  F: '灰色二级台阶/定制可装YJ电控+1双速泵',
  H: '黑色ABS二级台阶',
  J: '黑色一级台阶',
  K: 'PP/黑色二级台阶',
  L: 'PP/灰色二级台阶',
  M: 'PP/青棕色二级台阶',
  N: 'PS/棕色二级台阶',
  O: 'PS/灰色二级台阶',
  P: 'PS/黑橡木色二级台阶'
}

export const OUTDOOR_COVER_CODES = {
  '0': '无缸盖',
  A: '灰色常规厚度缸盖',
  B: '灰色加厚90-120缸盖',
  C: '灰色加厚100-125缸盖',
  E: '灰色常规厚度缸盖+常规缸盖支架',
  F: '棕色常规厚度缸盖+常规缸盖支架',
  G: '灰色加厚100-125带铝膜缸盖',
  H: '灰色加厚100-125带防水新材料缸盖',
  I: '黑色常规厚度缸盖',
  J: '灰色常规厚度带铝膜缸盖',
  K: '黑色加厚100-125缸盖',
  M: '棕色常规厚度缸盖',
  Q: '银色缸罩',
  R: '棕色常规厚度缸盖+银色缸罩',
  S: '缸盖支架',
  T: '银色缸罩（Heaven spa商标）',
  U: '灰色常规厚度缸盖+缸罩（Heaven spa商标）',
  W: '灰色加厚100-125缸盖+银色缸罩'
}

export const OUTDOOR_EXTERNAL_CODES = {
  '0': '无外接加热管路',
  '1': '手动进排水+贝拉乔logo灯+2米电源线',
  '2': '电动进排水+贝拉乔logo灯',
  '3': '手动进排水+2米电源线',
  A: '外接加热器预装管道（裙边上不预留接口）',
  B: 'Balboa辅助加热器',
  E: '带热泵预装管路（裙边上不预留接口）',
  F: '带热泵预装管路（裙边上预留接口）',
  K: '带Balboa热泵',
  L: '带热泵预装管路（裙边上预留接口/配双速泵用）',
  M: '带热泵预装管路（裙边上不预留接口/配双速泵用）',
  O: '带Gecko热泵（5KW/美标）',
  P: '带Gecko热泵（5KW）',
  Q: '带Gecko热泵（Mini热泵）',
  Z: '电动进排水+贝拉乔logo灯+2米电源线'
}

export const OUTDOOR_PACKAGING_CODES = {
  A: '铁托盘包装（立放）',
  B: '空缸木托盘叠装',
  C: '铁托盘包装（立放）（产品高970）',
  D: '木托盘包装（平放）',
  E: '铁托盘包装（立放）',
  F: '铁托盘包装（平放）',
  G: '全夹板包装（立放）',
  H: '全夹板包装/夹板带客户Logo（平放）',
  I: '木托盘包装（立放）',
  J: '木托盘包装（立放）（产品高970）',
  K: '铁托盘包装（立放）（带浅灰浴枕）',
  Z: '木托盘包装（特殊）'
}

export const POOL_COLOR_SUPPORT_CODES = {
  '1': '进口云彩白+镀锌铁支架',
  '2': '进口云彩黑+镀锌铁支架',
  A: '进口云彩白+常规焊接铝架',
  B: '进口云彩黑+常规焊接铝架',
  N: '进口云彩白/无支架',
  J: '进口石膏白+镀锌铁支架'
}

export const GLASS_WINDOW_CODES = {
  '0': '无玻璃窗',
  A: '带玻璃窗'
}

// ---------------- 泳池专用编码 ----------------
export const POOL_SHELL_CODES = {
  '1': '进口云彩白+镀锌铁支架',
  '2': '进口云彩黑+镀锌铁支架',
  A: '进口云彩白+常规焊接铝架',
  B: '进口云彩黑+常规焊接铝架',
  J: '进口石膏白+镀锌铁支架',
  N: '进口云彩白/无支架'
}

export const POOL_NOZZLE_CODES = {
  '00': '无喷嘴',
  '1A': '眉毛水喷（标准）',
  '1B': '眉毛水喷+气喷（标准）',
  '1C': '眉毛气泡改水喷',
  '1F': '眉毛水喷带灯',
  '1H': '眉毛增加水喷',
  '1I': '眉毛气改水再增加水喷眉毛水喷带灯+气喷改无气水喷',
  '1J': '特殊配置',
  '1K': '趟位气泡改水喷+气喷',
  '1N': '额外增加水喷（不带气喷）',
  '1P': '眉毛气改水+河喷',
  '1Q': '增加泳池喷',
  '1S': '眉毛增加水喷（带气喷）',
  '1T': '眉毛水喷带灯+瀑布',
  '1U': '眉毛水喷带灯+气喷',
  '1X': '泳池简配/老款泳池简配',
  '1Y': '老款泳池豪配',
  '1Z': '眉毛水喷+3个河喷',
  '11': '泳池带灯标配（老款泳池豪配带灯）',
  '12': '泳池带灯豪配（老款泳池豪配带灯）',
  '2A': '猫眼水喷（标准）',
  '2B': '猫眼水喷+气喷（标准）',
  '2H': '泳池猫眼水喷+6个泳池喷',
  '2G': '泳池猫眼水喷+气喷+3个河喷',
  '2P': '猫眼气改水+河喷',
  '22': '猫眼标准水喷+3个河喷（瑞典配置）',
  '5A': '钻石标准水喷',
  '5B': '钻石标准水喷+气喷'
}

export const POOL_POWER_CODES = {
  '0': '无电源标准',
  A: '220-240V/50HZ',
  B: '双110V/60HZ',
  C: '380V/50HZ'
}

export const POOL_CONTROL_CODES = {
  '00': '无控制器',
  '11': 'YE-5+K1000+3KW(带热泵功能）',
  '13': 'YE-5+K806+3.6KW（泳池区）+YJ-3+K506+3KW（户外缸区）',
  '15': 'YJ-3+K1000+3KW（泳池区）+YE-5+K1000+3KW（户外缸区）',
  '16': 'YJ-3+K300+4KW(1个泵）/YJ-3+K506+3KW（泳池区）+YE-5+K806+3KW（户外缸区）',
  '17': 'YJ-3+K1000+4KW/YE-5+K1000+3.6KW（泳池区）+YJ-3+K1000+3KW（户外缸区）',
  '18': 'YE-5+K506+3.6KW（配gecko热泵用）',
  '19': 'YJ-2+K300+4KW(1个泵）',
  '1B': 'YJ-2+K300+3KW（泳池区）+YJ-3+K506+3KW（户外缸区）/YJ-2+K300+3KW',
  '1C': 'YJ-2+K506+3KW',
  '1G': 'YJ-3+K506+3KW/YE-5+K806+3KW（泳池区）+YJ-3+K506+3KW（户外缸区）',
  '1H': 'YE-5+K506+3KW/YE-5+K806+3.6KW（泳池区）+YE-5+K506+3KW（户外缸区）',
  '1I': 'YE-5+K506+3.6KW/YE-5+K806+3KW（泳池区）+YE-5+K506+3KW（户外缸区）',
  '1J': 'YE-5+K806+3KW',
  '1K': 'YE-5+K806+3.6KW',
  '1L': 'YE-5+K1000+3KW',
  '1M': 'YE-5+K1000+3.6KW',
  '1N': 'YJ-3+K300+3KW（1个泵）',
  '1P': 'YE-5+K1000+3KW（泳池区/配2-3个泵选用）+YJ-3+K506+3KW（户外缸区/配1个泵选用）/YJ-3+K506+4KW',
  '1R': 'YE-3+K506+3KW',
  '1S': 'YE-3+K300+3KW(1个泵）',
  '2T': 'BP2100 G0+TP800+3KW',
  '2U': 'BP2100 G1+T型触摸面板+3KW',
  '2W': 'BP2100 G1+TP800+3KW',
  '35': 'YE-5+K1000+4KW（泳池区/配2-3个泵选用）+YJ-3+K1000+4KW（户外缸区/配1个泵选用）（美标）',
  '36': 'YE-5+K806+4KW（泳池区/配2-3个泵选用)）+YJ-3+K506+4KW（户外缸区/配1个泵选用）（美标）',
  '3B': 'YJ-2+K300+4KW(美标/配1个泵选用)',
  '3G': 'YJ-3+K506+4KW(美标/配1个泵选用)',
  '3J': 'YE-5+K806+4KW(美标/配2-3个泵选用)/YE-5+K806+4KW（泳池区/配2-3个泵选用）+YE-5+K806+4KW（户外缸区/配2-3个泵选用）(美标）',
  '3L': 'YE-5+K1000+4KW(美标/配2-3个泵选用)',
  '3N': 'YJ-3+K300+4KW(美标/配1个泵选用)',
  '3R': 'YE-5+K806+4KW（泳池区/配2-3个泵选用）+YE-5+K506+4KW（户外缸区/配2-3个泵选用）(美标）',
  '4U': 'BP2000+T型触摸面板+5.5KW（美标）',
  '55': 'P69B133+PB565+4KW（泳池区）+P68B123+PB565+4KW（户外缸区）'
}

export const POOL_WATER_PUMP_CODES = {
  '00': '无水泵',
  '11': '1个循环LX+3个2.5寸接口3HP单速泵LX+砂缸',
  '12': '1个gecko循环泵系统+砂缸',
  '1A': '1个循环泵Gecko+2个2.5寸接口3HP单速泵3LX+1个2寸接口3HP单速泵LX/1个循环泵Gecko+1个2寸接口3HP单速泵LX+游泳机680（220V）/1个循环泵Gecko+3个2.5寸接口3HP单速泵LX+1个2寸接口3HP单速泵LX/1个循环泵LX+游泳机680（220V/带无线遥控防水手表）',
  '1B': '1个循环泵LX+1个2寸接口3HP单速泵LX+游泳机680（220V/带无线遥控防水手表）/1个循环泵LX+游泳机680（220V/带无线遥控防水手表）+1个1HP水泵',
  '1C': '1个循环泵LX+游泳机680（380V/带无线遥控防水手表）+1个1HP水泵/2个循环泵Gecko+3个2.5寸接口3HP单速泵LX+2个2寸接口3HP单速泵Gecko',
  '1D': '1个循环泵LX+2个2.5寸接口3HP单速泵3LX+1个2寸接口3HP单速泵LX/1个循环泵LX+游泳机800（220V/带无线遥控防水手表）+1个1HP水泵',
  '1E': '1个循环LX+3个2.5寸接口3HP单速泵LX',
  '1H': '1个循环LX+3个2.5寸接口3HP单速泵LX+1个2寸接口3HP单速泵LX/1个循环泵LX+1个2寸接口3HP单速泵LX+游泳机680（220V）/2个循环泵LX+1个2寸接口3HP单速泵LX+游泳机680（220V）/2个循环LX+3个2.5寸接口3HP单速泵LX+2个2寸接口3HP单速泵LX',
  '1I': '1个循环泵LX+2个2.5寸接口3HP单速泵LX+1个2寸接口3HP单速泵LX/2个循环泵LX+3个2.5寸接口3HP单速泵LX+1个2寸接口3HP单速泵LX',
  '1J': '2个循环泵gecko+4个3HP单速泵LX',
  '1K': '2个循环泵gecko+4个3HP单速泵gecko',
  '1P': '2个循环泵LX+4个3HP单速泵LX',
  '1R': '1个循环泵Gecko+3个3HP单速泵Gecko/2个循环泵Gecko+5个3HP单速泵Gecko',
  '1S': '1个循环泵Gecko+3个2寸接口3HP单速泵LX',
  '1T': '1个循环LX+2个2.5寸接口3HP单速泵LX/1个循环泵LX+3个3HP单速泵LX/1个循环LX+3个2.5寸接口3HP单速泵LX/2个循环泵LX+5个3HP单速泵LX',
  '1U': '1个循环泵LX+3个3HP单速泵LX+1个2HP单速LX',
  '1Y': '1个循环泵LX+4个3HP单速泵LX',
  '2I': '1个2.5HP双速泵LX+2个3HP单速泵LX',
  '2K': '1个3HP双速泵LX+2个3HP单速泵LX',
  '2P': '2个3HP双速泵LX+2个3HP单速泵LX',
  '33': '1个循环泵LX+2个2.5寸接口3HP单速泵LX+1个2寸接口3HP单速泵Gecko（美标）/1个循环LX+3个2.5寸接口单速3HPLX+1个2寸接口单速3HPGecko（美标）/2个循环泵LX+3个2.5寸接口3HP单速泵LX+1个2寸接口3HP单速泵Gecko(美标）',
  '37': '1个循环LX+3个2.5寸接口4HP单速泵LX+1个2寸接口3HP单速泵Gecko（美标）',
  '38': '1个循环泵LX+4个3HP单速泵Gecko（美标）/2个循环泵LX+5个3HP单速泵Gecko（美标）',
  '3A': '1个循环泵Gecko+3个2.5寸接口3HP单速泵LX+1个2寸接口3HP单速泵LX（美标）/1个循环泵Gecko+1个2寸接口3HP单速泵LX+游泳机680（美标）/2个循环泵Gecko+3个2.5寸接口3HP单速泵LX+1个2寸接口3HP单速泵LX（美标）/2个循环泵Gecko+3个2.5寸接口3HP单速泵LX+2个2寸接口3HP单速泵LX(美标）',
  '3B': '1个循环泵Gecko+2个2.5寸接口3HP单速泵LX+1个2寸接口3HP单速泵LX（美标）',
  '3C': '1个循环泵Gecko+3个2.5寸接口4HP单速泵LX+1个2寸接口3HP单速泵Gecko（美标）/1个循环泵Gecko+3个2.5寸接口3HP单速泵LX+1个2寸接口3HP单速泵Gecko（美标）/2个循环泵Gecko+3个2.5寸接口3HP单速泵LX+2个2寸接口3HP单速泵Gecko(美标）',
  '3D': '1个循环泵Gecko+1个2寸接口3HP单速泵LX（美标）/1个循环LX+2个2.5寸接口4HP单速泵LX+1个2寸接口3HP单速泵LX(美标）',
  '3F': '1个循环LX+3个2.5寸接口4HP单速泵LX+1个2寸接口3HP单速泵LX（美标）/2个循环LX+3个2.5寸接口4HP单速泵LX+2个2寸接口3HP单速泵LX(美标）',
  '3H': '1个循环泵LX+3个2.5寸接口3HP单速泵LX+1个2寸接口3HP单速泵LX（美标）/2个循环LX+3个2.5寸接口3HP单速泵LX+2个2寸接口3HP单速泵LX(美标）',
  '3I': '1个循环泵LX+2个2.5寸接口3HP单速泵LX+1个2寸接口3HP单速泵LX（美标）/2个循环泵LX+3个2.5寸接口3HP单速泵LX+1个2寸接口3HP单速泵LX（美标）',
  '3J': '1个循环泵Gecko+2个2寸接口3HP单速泵LX（美标）',
  '3K': '1个循环泵Gecko+2个3HP单速泵Gecko（美标）',
  '3L': '2个循环泵Gecko+4个3HP单速泵Gecko（美标）',
  '3P': '2个循环泵LX+4个3HP单速泵LX（美标）',
  '3R': '1个循环泵Gecko+3个3HP单速泵Gecko（美标）/2个循环泵Gecko+5个3HP单速泵Gecko（美标）',
  '3S': '1个循环泵Gecko+3个2寸接口3HP单速泵LX（美标）/2个循环泵Gecko+5个3HP单速泵LX（美标）',
  '3T': '1个循环泵LX+3个3HP单速泵LX（美标）',
  '3U': '1个循环泵Gecko+4个3HP单速泵LX（美标）',
  '3V': '1个循环泵LX+3个3HP单速泵LX+1个1HP单速（美标）/2个循环泵LX+4个3HP单速泵LX+1个1HP单速（美标）',
  '3W': '1个循环LX+3个2.5寸接口3HP单速泵LX+1个1HP单速(美标）/2个循环LX+3个2.5寸接口3HP单速泵LX+2个2寸接口3HP单速泵LX+1个1HP单速(美标）',
  '3X': '1个循环泵Gecko+4个3HP单速泵Gecko（美标）',
  '4J': '1个3HP双速泵LX+2个3HP单速泵LX（美标）',
  '4K': '1个3HP双速泵Gecko+2个3HP单速泵Gecko（美标）',
  '4T': '1个3HP双速泵LX+3个3HP单速泵LX（美标）',
  '4U': '1个3HP双速泵Gecko+3个3HP单速泵Gecko（美标）/2个3HP双速泵Gecko+3个3HP单速泵Gecko（美标）',
  '6Y': '1个双速泵+3个单速泵管路（2.5寸管路/无泵）'
}

export const POOL_AIR_PUMP_CODES = {
  '0': '无风泵',
  A: '1个0.9HP风泵',
  B: '1个0.9HP风泵+香薰',
  K: '1个0.9HP加热风泵+腾龙/LVJ香薰'
}

export const POOL_SANITATION_CODES = {
  '0': '无消毒系统',
  A: '臭氧',
  B: 'UV',
  C: '臭氧+UV',
  D: '臭氧+盐氯预装管',
  E: 'UV+盐氯预装管',
  F: '臭氧+UV+盐氯预装管',
  G: '臭氧+IN.Clear',
  H: '臭氧（美标）',
  I: '臭氧管路（无臭氧）',
  J: 'IN.Clear',
  K: '臭氧+ClearBlue（美标）',
  L: '臭氧+IN.Clear(泳池区）+臭氧+盐氯预装管道(SPA区）',
  M: '臭氧+UV（美标）'
}

export const POOL_MULTIMEDIA_CODES = {
  '0': '无多媒体',
  '2': '普兰高配蓝牙+低音炮+2个共振喇叭+gecko-wifi（澳标wifi）（停用）/普兰高配蓝牙+低音炮+2个共振喇叭+2套gecko-wifi（澳标wifi）（停用）',
  '4': 'GECKO-WIFI（澳标）',
  '5': '普兰高配蓝牙+低音炮+2个缸面喇叭（美标）/普兰高配蓝牙+低音炮+4个缸面喇叭（美标）',
  '8': 'GECKO蓝牙+低音炮+2个缸面喇叭（美标）/GECKO蓝牙+低音炮+4个缸面喇叭（美标）',
  A: 'GECKO蓝牙+低音炮+2个缸面喇叭/GECKO蓝牙+低音炮+4个缸面喇叭/GECKO蓝牙+低音炮+4个共振喇叭（欧标/美标通用）',
  B: 'GECKO-WIFI/2套GECKO-WIFI',
  C: 'GECKO蓝牙+WIFI+低音炮+2个缸面喇叭（美标）/GECKO蓝牙+WIFI+低音炮+4个缸面喇叭（美标）/GECKO蓝牙+WIFI+低音炮+4个共振喇叭（美标）/GECKO蓝牙+2套WIFI+低音炮+4个缸面喇叭（美标）/GECKO蓝牙+2套WIFI+低音炮+4个共振喇叭',
  D: 'BALBOA蓝牙+低音炮+4个共振喇叭',
  E: 'BALBOA-WIFI/2套BALBOA-WIFI',
  F: 'BALBOA蓝牙+WIFI+低音炮+4个共振喇叭/BALBOA蓝牙+2套WIFI+低音炮+4个共振喇叭',
  G: '普兰低配蓝牙+2个共振喇叭',
  H: '普兰高配蓝牙+低音炮+2或4个缸面喇叭或2个共振喇叭（停用）',
  M: '普兰高配蓝牙+低音炮+2个共振喇叭+gecko-wifi或2套gecko-wifi（停用）',
  N: '普兰高配蓝牙+低音炮+2个共振喇叭+BALBOA-WIFI（停用）',
  O: 'Balboa蓝牙（带有源低音炮）+4个共振喇叭',
  P: 'GECKO-WIFI（美标）',
  Q: '只带3个共振喇叭',
  R: 'GECKO蓝牙+WIFI+低音炮+4个共振喇叭（美标）（停用）/GECKO蓝牙+2套WIFI+低音炮+4个共振喇叭（美标）',
  S: '普兰低配蓝牙+2个共振喇叭（美标）',
  U: '普兰高配蓝牙+低音炮+2个共振喇叭（美标）',
  V: '方形蓝牙带内置低音炮+2/4个缸面喇叭或2个共振喇叭',
  W: '方形蓝牙带内置低音炮+Gecko-wifi',
  X: '普兰高配蓝牙+低音炮+2个共振喇叭+gecko-wifi（美标）/2套gecko-wifi（美标）',
  Y: 'GECKO蓝牙+低音炮+4个共振喇叭（欧标/美标通用）'
}

export const POOL_LIGHTING_CODES = {
  '0': '无灯光系统',
  A: '水底灯',
  B: '水底灯+阀带灯',
  C: '水底灯+阀带灯+缸边灯',
  D: '水底灯+阀带灯+缸边灯+转角灯',
  E: '水底灯+阀带灯+缸边灯+光千灯',
  F: '水底灯+阀带灯+缸边灯+转角灯+裙边灯',
  I: '水底灯+阀带灯+裙边灯（补单用）',
  J: '水底灯+阀带灯+缸边灯+3个灯杯座+转角灯+裙边灯(增加灯杯座）',
  L: '水底灯+阀带灯+缸边灯+转角灯+裙边灯(无灯杯座）',
  N: '水底灯+阀带灯+缸边灯（配YJ电控用）',
  O: '水底灯+阀带灯+缸边灯+转角灯+裙边灯（配YJ电控用）',
  U: '水底灯+阀带灯+缸边灯+转角灯+裙边灯+贝拉乔logo灯',
  V: '水底灯+阀带灯+缸边灯+2个灯杯座+转角灯带+裙边灯带+贝拉乔logo灯'
}

export const POOL_BOTTOM_INSULATION_CODES = {
  '0': '无底',
  A: '单底',
  B: '半三明治底',
  C: '全三明治底',
  E: '全三明治底支架（配镀锌支架）'
}

export const POOL_SIDE_INSULATION_CODES = {
  '0': '无缸侧保温',
  A: '四面保温板',
  B: '帘子保温',
  C: '电机面保温板'
}

export const POOL_BODY_INSULATION_CODES = {
  '0': '无缸体保温',
  A: '单层发泡',
  B: '满泡',
  D: '2cm厚发泡'
}

export const POOL_SKIRT_CODES = {
  '0': '无裙边',
  A: '灰色生态裙边',
  C: '咖啡色生态裙边',
  D: '灰色铝裙边',
  K: '灰色铝裙边(配玻璃窗用）',
  M: '灰色/铝板贴膜聚氨酯裙边（配玻璃窗用）',
  N: '灰色/铝板贴膜聚氨酯裙边',
  P: '棕色/铝板贴膜聚氨酯裙边',
  T: '双面色/灰色+棕色/铝板贴膜聚氨酯裙边',
  X: '单面色/黑橡木网纹铝板聚氨酯裙边'
}

export const POOL_CORNER_CODES = {
  '0': '无转角',
  A: '灰色生态转角/R320',
  D: '灰色铝转角',
  E: '咖啡色铝转角',
  F: '棕色铝转角',
  P: '黑橡木PS转角',
  Q: '黑橡木铝转角'
}

export const POOL_STAIRS_CODES = {
  '0': '无台阶',
  B: 'PS/柚木色三级台阶',
  D: '咖啡色三级台阶/PS/咖啡色三级台阶',
  G: 'PS/灰色三级台阶',
  I: '灰色台阶带扶手',
  N: 'PS/棕色三级台阶',
  O: 'PS/黑橡木色三级台阶'
}

export const POOL_COVER_CODES = {
  '0': '无缸盖',
  D: '灰色厚度100-150缸盖',
  E: '灰色厚度100-150缸盖+常规缸盖支架（2个支架）',
  F: '青棕色缸盖+常规缸盖支架（2个支架）',
  H: '灰色厚度100-150缸盖',
  I: '黑色厚度100-150缸盖',
  M: '棕色厚度100-150缸盖',
  N: '黑色厚度100-150缸盖带铝膜带防水织布',
  Q: '灰色厚度100-150缸盖+银色缸罩',
  R: '棕色厚度100-150缸盖+银色缸罩',
  T: '黑色缸盖（带客户Logo）+常规缸盖支架（2个支架）',
  U: '灰色厚度100-150缸盖（带客户Logo）',
  V: '黑色缸盖+常规缸盖支架（2个支架）',
  X: '电动卷帘盖子',
  Y: '深灰色软缸盖',
  Z: '黑色软缸盖'
}

export const POOL_EXTERNAL_CODES = {
  '0': '无外接加热管路',
  '1': '手动进排水+贝拉乔logo灯+2米电源线',
  '2': '带电动进排水+贝拉乔logo灯',
  A: '1套外接加热器预装管道',
  B: 'Balboa辅助加热器',
  C: '1套外接加热器预装管道+1个不锈钢扶手',
  D: '1个不锈钢扶手',
  E: '带热泵预装管道/SPA和泳池区带热泵预装管道',
  F: '带热泵预装管道（裙边上预留接口）/SPA区和泳池区带热泵预装管道（裙边上预留接口）',
  G: '带热泵预装管（裙边上预留接口）+吊杆+划桨',
  H: '吊杆',
  I: '吊杆+划桨',
  J: '带热泵预装管道+吊杆+划桨/SPA区和泳池区带热泵预装管道+泳池区吊杆+泳池区划桨',
  K: '带热泵',
  L: '带GECKO热泵（5KW）+手动进排水+2米电源线+贝拉乔logo灯',
  Q: '带Gecko热泵（Mini热泵）',
  X: '带热泵预装管道(裙边上预留接口)+带电动进排水+贝拉乔logo灯+2米电源线',
  Y: '手动进排水+贝拉乔logo灯',
  Z: '带电动进排水+贝拉乔logo灯+2米电源线'
}

export const POOL_PACKAGING_CODES = {
  A: '常规包装',
  B: '叠装',
  Z: '常规包装（瑞典）'
}

// ---------------- 冰水缸专用编码 ----------------
// 2 位组合码：首位颜色/配置，次位孔位
export const ICE_TUB_COLOR_HOLE_CODES = {
  A1: '进口云彩白 + 无喷嘴/ 白色/开孔 + 无喷嘴',
  A2: '进口云彩白 + 标准孔',
  B1: '进口云彩黑 + 无喷嘴',
  B2: '进口云彩黑 + 标准孔',
  M1: '国产全白 + 无喷嘴',
  M2: '国产全白 + 标准孔',
  Q1: '内缸黑色+外缸白色 + 无喷嘴',
  Q2: '内缸黑色+外缸白色 + 标准孔',
  R1: '内缸白色+外缸黑色 + 无喷嘴',
  R2: '内缸白色+外缸黑色 + 标准孔'
}

export const ICE_TUB_NOZZLE_CODES = {
  '00': '无喷嘴',
  '1A': '眉毛喷嘴/标准孔'
}

export const ICE_TUB_POWER_CODES = {
  '0': '无电源标准',
  A: '220-240V/50Hz',
  B: '双110V/60Hz',
  C: '220-240V/50Hz英插',
  E: '220-240V/50Hz欧插（16A）',
  F: '380V/50HZ',
  G: '220-240V/50Hz澳插（10A）',
  H: '单110V/60Hz美插（配漏保转换器）',
  I: '单110V/60Hz美插带漏保',
  L: '220-240V/50Hz欧插带漏保（16A）',
  M: '220V/60Hz美插',
  N: '220V/60Hz美插带漏保/菲律宾'
}

export const ICE_TUB_CONTROL_CODES = {
  '00': '无控制器',
  '1A': 'P16B162+PB557-02',
  '1B': 'P16B162+PB565-000',
  '1E': 'P68B123-001+PB565-001+4KW',
  '3A': 'P16B162+PB557-02（美标）',
  '3B': 'P16B162+PB565-000（美标）',
  '3C': 'P68B123-001+PB565-001+4KW（美标/面板带Joyonway商标）',
  '3D': 'P16B162+PB565-000（欧标/美标通用/带WIFI功能/带客户logo）',
  '3E': 'P16B162+PB565-000（欧标/美标通用/带WIFI功能/带客户logo）(停用）',
  '3F': 'P16B162+PB565-000（欧标/美标通用/带WIFI功能/带贝拉乔logo）',
  '5D': 'P68B123-001+PB565-001+4KW（欧标/美标通用/带WIFI功能/带客户logo）',
  '5E': 'P68B123-001+PB565-001+4KW（美标）',
  '5F': 'P68B123-001+PB565-001+4KW（欧标/美标通用/带WIFI功能/带贝拉乔logo）'
}

export const ICE_TUB_WATER_PUMP_CODES = {
  '00': '无水泵',
  '1B': '2个循环泵+1个单速2HPLX',
  '1C': '1个循环泵',
  '2B': '冰水区1个循环+按摩区1个双速2HPLX',
  '3C': '1个循环泵（美标/单110V）',
  '3D': '1个循环泵（美标/单110V/大功率）',
  '3F': '2个循环泵+1个单速2HPLX（美标/单110V）',
  '3I': '1个循环泵（220V/60HZ）',
  '4B': '冰水区1个循环+按摩区1个双速2HPLX（美标/单110V）',
  '4D': '冰水区1个循环+按摩区1个双速2HPLX（美标/单110V）/管路带防冻功能'
}

export const ICE_TUB_AIR_PUMP_CODES = {
  '0': '无风泵'
}

export const ICE_TUB_SANITATION_CODES = {
  '0': '无消毒系统',
  A: '臭氧',
  B: 'UV',
  H: '臭氧（美标）',
  N: 'UV（美标）'
}

export const ICE_TUB_MULTIMEDIA_CODES = {
  '0': '无多媒体',
  G: '普兰简配蓝牙+共振喇叭',
  S: '普兰简配蓝牙+共振喇叭（美标）',
  U: '普兰豪配蓝牙+低音炮（美标）'
}

export const ICE_TUB_LIGHTING_CODES = {
  '0': '无灯光系统',
  A: '水底灯',
  D: '水底灯+阀带灯+缸边灯+转角灯',
  T: '水底灯+贝拉乔logo灯'
}

export const ICE_TUB_BOTTOM_INSULATION_CODES = {
  '0': '无支架',
  A: '玻璃纤维/单底支架',
  B: '玻璃纤维/半三明治底支架',
  C: '玻璃纤维/全三明治底支架',
  K: '单底镀锌支架',
  L: '无底支架（停用）',
  P: '玻璃纤维/全三明治底支架(配镀锌支架)'
}

export const ICE_TUB_SIDE_INSULATION_CODES = {
  '0': '无缸侧保温',
  A: '四面保温板',
  C: '电机面保温板'
}

export const ICE_TUB_BODY_INSULATION_CODES = {
  '0': '无缸体保温',
  A: '户外缸单层发泡',
  B: 'SPA区单泡+冰水区满泡',
  C: 'SPA区满泡+冰水区满泡'
}

export const ICE_TUB_SKIRT_CODES = {
  '0': '无裙边',
  A: '灰色木纹铝塑板裙边/外缸',
  B: '实木裙边（刷木蜡油）',
  N: '灰色/铝板贴膜聚氨酯裙边',
  O: '双面色/黑橡木网纹铝板聚氨酯裙边',
  P: '棕色/铝板贴膜聚氨酯裙边',
  S: '实木裙边（普通）',
  X: '单面色/黑橡木网纹铝板聚氨酯裙边'
}

export const ICE_TUB_CORNER_CODES = {
  '0': '无转角',
  D: '灰色铝转角',
  F: '棕色铝转角',
  P: '黑橡木PS转角',
  Q: '黑橡木铝转角'
}

export const ICE_TUB_STAIR_CODES = {
  '0': '无台阶',
  A: 'PS/灰色一级台阶',
  B: '实木台阶（刷木蜡油）',
  L: '实木台阶（普通）'
}

export const ICE_TUB_COVER_CODES = {
  '0': '无缸盖',
  I: '黑色防水织布四叠缸盖'
}

export const ICE_TUB_EXTERNAL_CODES = {
  '0': '无热泵',
  K: '带Balboa热泵',
  L: '带Balboa热泵（美标/单110V）',
  N: '带Balboa热泵（220V/60HZ）'
}

export const ICE_TUB_PACKAGING_CODES = {
  A: '木托盘包装（平放）',
  B: '空缸木托盘叠装',
  G: '全夹板包装（平放）',
  H: '全夹板包装/夹板带客户Logo（平放）',
  Z: '木托盘包装（客户定制）'
}

export const POWER_STANDARD_CODES = {
  '0': '标注错误（无此配置）',
  A: '220V/50HZ、双110V/60HZ',
  B: '220-240V/50Hz英插',
  C: '220-240V/50Hz澳插（15A）',
  D: '220-240V/50Hz欧插（13A/16A）',
  E: '380V/50HZ',
  F: '220-240V/50Hz澳插（10A）',
  G: '110V/60Hz美插 带转换器',
  H: '110V/60Hz美插带漏保',
  I: '220/60Hz',
  J: '220/50Hz国插带漏保（16A）',
  K: '220-240V/50Hz欧插带漏保（16A）',
  L: '220V/60Hz带美插带漏保',
  M: '110V/60HZ'
}

export const BOM_TYPES = [
  { value: 'outdoor', label: '户外缸' },
  { value: 'pool', label: '泳池' },
  { value: 'iceTub', label: '冰水缸' }
]

const createSection = (params) => params

export const BOM_CONFIG = {
  outdoor: [
    createSection({
      key: 'colorHole',
      label: '第1+2位（缸体颜色+开孔配置）',
      digits: 2,
      options: OUTDOOR_COLOR_HOLE_CODES
    }),
    createSection({
      key: 'nozzle',
      label: '第3+4位（喷嘴配置）',
      digits: 2,
      options: OUTDOOR_NOZZLE_CODES
    }),
    createSection({
      key: 'powerStandard',
      label: '第5位（电源标准）',
      digits: 1,
      options: OUTDOOR_POWER_CODES
    }),
    createSection({
      key: 'controlSystem',
      label: '第6+7位（控制系统）',
      digits: 2,
      options: OUTDOOR_CONTROL_CODES
    }),
    createSection({
      key: 'waterPump',
      label: '第8+9位（水泵配置）',
      digits: 2,
      options: OUTDOOR_WATER_PUMP_CODES
    }),
    createSection({
      key: 'airPump',
      label: '第10位（风泵配置）',
      digits: 1,
      options: OUTDOOR_AIR_PUMP_CODES
    }),
    createSection({
      key: 'sanitation',
      label: '第11位（消毒系统）',
      digits: 1,
      options: OUTDOOR_SANITATION_CODES
    }),
    createSection({
      key: 'multimedia',
      label: '第12位（多媒体）',
      digits: 1,
      options: OUTDOOR_MULTIMEDIA_CODES
    }),
    createSection({
      key: 'lighting',
      label: '第13位（灯光配置）',
      digits: 1,
      options: OUTDOOR_LIGHTING_CODES
    }),
    createSection({
      key: 'bottomInsulation',
      label: '第14位（底保温）',
      digits: 1,
      options: OUTDOOR_BOTTOM_CODES
    }),
    createSection({
      key: 'sideInsulation',
      label: '第15位（侧保温配置）',
      digits: 1,
      options: OUTDOOR_SIDE_INSULATION_CODES
    }),
    createSection({
      key: 'bodyInsulation',
      label: '第16位（缸体保温）',
      digits: 1,
      options: OUTDOOR_BODY_INSULATION_CODES
    }),
    createSection({
      key: 'skirt',
      label: '第17位（裙边）',
      digits: 1,
      options: OUTDOOR_SKIRT_CODES
    }),
    createSection({
      key: 'corner',
      label: '第18位（转角）',
      digits: 1,
      options: OUTDOOR_CORNER_CODES
    }),
    createSection({
      key: 'stairs',
      label: '第19位（台阶）',
      digits: 1,
      options: OUTDOOR_STAIR_CODES
    }),
    createSection({
      key: 'cover',
      label: '第20位（缸盖/缸罩）',
      digits: 1,
      options: OUTDOOR_COVER_CODES
    }),
    createSection({
      key: 'externalHeating',
      label: '第21位（外加热/吊杆/划桨/其他配置）',
      digits: 1,
      options: OUTDOOR_EXTERNAL_CODES
    }),
    createSection({
      key: 'packaging',
      label: '第22位（包装）',
      digits: 1,
      options: OUTDOOR_PACKAGING_CODES
    })
  ],
  pool: [
    createSection({
      key: 'poolShell',
      label: '第1位（缸体颜色+支架配置）',
      digits: 1,
      options: POOL_SHELL_CODES
    }),
    createSection({
      key: 'nozzle',
      label: '第2+3位（喷嘴）',
      digits: 2,
      options: POOL_NOZZLE_CODES
    }),
    createSection({
      key: 'powerStandard',
      label: '第4位（电源标准）',
      digits: 1,
      options: POOL_POWER_CODES
    }),
    createSection({
      key: 'controlSystem',
      label: '第5+6位（控制系统）',
      digits: 2,
      options: POOL_CONTROL_CODES
    }),
    createSection({
      key: 'waterPump',
      label: '第7+8位（水泵）',
      digits: 2,
      options: POOL_WATER_PUMP_CODES
    }),
    createSection({
      key: 'airPump',
      label: '第9位（风泵）',
      digits: 1,
      options: POOL_AIR_PUMP_CODES
    }),
    createSection({
      key: 'sanitation',
      label: '第10位（消毒系统）',
      digits: 1,
      options: POOL_SANITATION_CODES
    }),
    createSection({
      key: 'multimedia',
      label: '第11位（多媒体）',
      digits: 1,
      options: POOL_MULTIMEDIA_CODES
    }),
    createSection({
      key: 'lighting',
      label: '第12位（灯光系统）',
      digits: 1,
      options: POOL_LIGHTING_CODES
    }),
    createSection({
      key: 'bottomInsulation',
      label: '第13位（底保温）',
      digits: 1,
      options: POOL_BOTTOM_INSULATION_CODES
    }),
    createSection({
      key: 'sideInsulation',
      label: '第14位（缸侧保温）',
      digits: 1,
      options: POOL_SIDE_INSULATION_CODES
    }),
    createSection({
      key: 'bodyInsulation',
      label: '第15位（缸体保温）',
      digits: 1,
      options: POOL_BODY_INSULATION_CODES
    }),
    createSection({
      key: 'skirt',
      label: '第16位（裙边）',
      digits: 1,
      options: POOL_SKIRT_CODES
    }),
    createSection({
      key: 'corner',
      label: '第17位（转角）',
      digits: 1,
      options: POOL_CORNER_CODES
    }),
    createSection({
      key: 'glassWindow',
      label: '第18位（玻璃窗）',
      digits: 1,
      options: GLASS_WINDOW_CODES
    }),
    createSection({
      key: 'stairs',
      label: '第19位（台阶）',
      digits: 1,
      options: POOL_STAIRS_CODES
    }),
    createSection({
      key: 'cover',
      label: '第20位（缸盖/缸罩）',
      digits: 1,
      options: POOL_COVER_CODES
    }),
    createSection({
      key: 'externalHeating',
      label: '第21位（外置加热）',
      digits: 1,
      options: POOL_EXTERNAL_CODES
    }),
    createSection({
      key: 'packaging',
      label: '第22位（包装）',
      digits: 1,
      options: POOL_PACKAGING_CODES
    })
  ],
  iceTub: [
    createSection({
      key: 'colorHole',
      label: '第1+2位（缸体颜色+开孔配置）',
      digits: 2,
      options: ICE_TUB_COLOR_HOLE_CODES
    }),
    createSection({
      key: 'nozzle',
      label: '第3+4位（喷嘴配置）',
      digits: 2,
      options: ICE_TUB_NOZZLE_CODES
    }),
    createSection({
      key: 'powerStandard',
      label: '第5位（电源标准）',
      digits: 1,
      options: ICE_TUB_POWER_CODES
    }),
    createSection({
      key: 'controlSystem',
      label: '第6+7位（控制系统）',
      digits: 2,
      options: ICE_TUB_CONTROL_CODES
    }),
    createSection({
      key: 'waterPump',
      label: '第8+9位（水泵配置）',
      digits: 2,
      options: ICE_TUB_WATER_PUMP_CODES
    }),
    createSection({
      key: 'airPump',
      label: '第10位（风泵配置）',
      digits: 1,
      options: ICE_TUB_AIR_PUMP_CODES
    }),
    createSection({
      key: 'sanitation',
      label: '第11位（消毒系统）',
      digits: 1,
      options: ICE_TUB_SANITATION_CODES
    }),
    createSection({
      key: 'multimedia',
      label: '第12位（多媒体）',
      digits: 1,
      options: ICE_TUB_MULTIMEDIA_CODES
    }),
    createSection({
      key: 'lighting',
      label: '第13位（灯光配置）',
      digits: 1,
      options: ICE_TUB_LIGHTING_CODES
    }),
    createSection({
      key: 'bottomInsulation',
      label: '第14位（支架+底保温）',
      digits: 1,
      options: ICE_TUB_BOTTOM_INSULATION_CODES
    }),
    createSection({
      key: 'sideInsulation',
      label: '第15位（侧保温配置）',
      digits: 1,
      options: ICE_TUB_SIDE_INSULATION_CODES
    }),
    createSection({
      key: 'bodyInsulation',
      label: '第16位（缸体保温）',
      digits: 1,
      options: ICE_TUB_BODY_INSULATION_CODES
    }),
    createSection({
      key: 'skirt',
      label: '第17位（裙边）',
      digits: 1,
      options: ICE_TUB_SKIRT_CODES
    }),
    createSection({
      key: 'corner',
      label: '第18位（转角）',
      digits: 1,
      options: ICE_TUB_CORNER_CODES
    }),
    createSection({
      key: 'stairs',
      label: '第19位（台阶）',
      digits: 1,
      options: ICE_TUB_STAIR_CODES
    }),
    createSection({
      key: 'cover',
      label: '第20位（缸盖/缸罩）',
      digits: 1,
      options: ICE_TUB_COVER_CODES
    }),
    createSection({
      key: 'externalHeating',
      label: '第21位（外加热/吊杆/划桨/其他配置）',
      digits: 1,
      options: ICE_TUB_EXTERNAL_CODES
    }),
    createSection({
      key: 'packaging',
      label: '第22位（包装）',
      digits: 1,
      options: ICE_TUB_PACKAGING_CODES
    })
  ]
}

export const createDefaultBomSelections = (type) => {
  const selections = {}
  const sections = BOM_CONFIG[type] || []
  sections.forEach((section) => {
    if (Array.isArray(section.children) && section.children.length) {
      section.children.forEach((child) => {
        selections[child.key] = ''
      })
    } else {
      selections[section.key] = ''
    }
  })
  return selections
}
