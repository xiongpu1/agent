# MultiAgent

本项目是一个基于 Vue 3 + Vite + Element Plus 的前端示例，包含首页产品列表、BOM 选择页，以及产品详情页（规格页/海报/说明书三种编辑与导出能力）。

## 快速开始

```sh
npm install
npm run dev
```

## 目录概览
- `src/views/Home.vue`：首页产品列表
- `src/views/ProductBoms.vue`：BOM 选择页
- `src/views/ProductDetail.vue`：产品详情页（规格页/海报/说明书）
- `src/router/index.js`：路由

---

# ProductDetail 三种内容的数据格式
产品详情页内部有三套可编辑模板：
- 规格页（promo）
- 海报（poster）
- 说明书（manual）

你可直接修改 `ProductDetail.vue` 中对应的初始 JSON 结构来定制，或在运行时通过路由 query 传入（如不需要通过 URL 传值，可忽略本段）。

## 1) 规格页（promo）数据结构
关键字段：
- `productTitle: string` 产品名称标题，支持在画布内直接编辑。
- `features: { capacity: string, jets: string, pumps: string }` 左列三大要素。
  - `capacity` 座位/容量数字。
  - `jets` 喷嘴数量。
  - `pumps` 水泵数量。
- `measurements: string` 尺寸文本（示例：`85" × 85" × 39"`）。
- `specs: string[]` 右列规格明细，数组下标含义固定：
  - `[0]` Cabinet Color 点阵颜色（以逗号分隔的颜色，例如 `#333,#999`）。
  - `[1]` Shell Color 点阵颜色（以逗号分隔）。
  - `[2]` Dry Weight（如 `180kg`）。
  - `[3]` Water Capacity（如 `1200L`）。
  - `[4]` Pump（如 `2x Jets Pump + 1x Circ Pump`）。
  - `[5]` Controls（如 `Balboa BP601`）。
- `premiumFeatures: string[]` 左列“Premium Lighting System”要点列表。
- `insulationFeatures: string[]` 左列“Energy-Saving Insulation System”要点列表。
- `extraFeatures: string[]` 左列“Extra Features”要点列表。
- `images: { product: string, background: string }` 顶部背景与产品主图。

示例：
```json
{
  "productTitle": "Vastera",
  "features": { "capacity": "4", "jets": "22", "pumps": "3" },
  "measurements": "85\" × 85\" × 39\"",
  "specs": [
    "#222,#444",           
    "#eee,#ccc",
    "180kg",
    "1200L",
    "2x Jets Pump + 1x Circ Pump",
    "Balboa BP601"
  ],
  "premiumFeatures": ["Premium Lighting", "Acrylic Shell"],
  "insulationFeatures": ["Full Foam", "Bottom Wrap"],
  "extraFeatures": ["Ozone", "UV Sterilizer"],
  "images": { "product": "/poster/product.png", "background": "/poster/back.png" }
}
```

## 2) 海报（poster）数据结构
关键字段：
- `background: string` 背景图 URL。
- `product: string` 海报中央产品主图。
- `leftTop/rightTop/rightMid/rightBottom/bottomLeft/bottomRight`: `{ img: string, cap: string }`
  - `img` 卡片图片。
  - `cap` 卡片说明文字（在画布内可编辑）。
- `hotNum: { value: string, zone: string }` 热区大数字与区域名（如 `104°F`, `SPA ZONE`）。
- `coldNum: { value: string, zone: string }` 冷区大数字与区域名（如 `42°F`, `COLD ZONE`）。
- `specs: { capacity: string, pumps: string, jets: string, measurements: string }` 海报底部规格行。

示例：
```json
{
  "background": "/poster/back.png",
  "product": "/poster/product.png",
  "leftTop": { "img": "/poster/image.png", "cap": "Spacious Footwear Area" },
  "rightTop": { "img": "/poster/image.png", "cap": "Anti-freeze System" },
  "hotNum": { "value": "104°F", "zone": "SPA ZONE" },
  "coldNum": { "value": "42°F", "zone": "COLD ZONE" },
  "specs": { "capacity": "4", "pumps": "3", "jets": "22", "measurements": "85\" × 85\" × 39\"" }
}
```

## 3) 说明书（manual）数据结构
说明书由 `meta` 和 `pages` 两部分组成。

- `meta`：侧栏目录信息
  - `title: string`
  - `toc: { title: string, page: number }[]`

- `pages: Page[]`
  - `Page.header?: string` 页眉标题
  - `Page.blocks: Block[]` 由多种块组成：
    - `heading`：`{ type: 'heading', text: string, level?: 1|2|3 }`
      - `text` 标题文本；`level` 标题级别（默认 1）。
    - `paragraph`：`{ type: 'paragraph', text: string, className?: string }`
      - `text` 段落文本；`className` 自定义类名（可用于字号/间距）。
    - `list`：`{ type: 'list', ordered: boolean, items: string[] }`
      - `ordered` 是否有序；`items` 列表项（支持基础 HTML）。
    - `image`：`{ type: 'image', src: string, alt?: string, fullWidth?: boolean, width?: number|string, height?: number|string, marginTop?: number, marginBottom?: number, rotate?: number, caption?: string }`
      - `fullWidth` 是否占满宽度；`width/height` 支持数值或 CSS 尺寸字符串；`rotate` 角度；`caption` 说明文字。
    - `imageFloat-<pos>`：`{ type: 'imageFloat-bottom-left' | 'imageFloat-bottom-right' | ... , src: string }`
      - 浮动图尺寸与位置通过 CSS `.img-float.<pos>` 控制（不通过 JSON 设置）。
    - `table`：`{ type: 'table', headers?: string[], rows: string[][] }`
      - `headers` 表头数组（可选）；`rows` 行数据二维数组。
    - `grid4`：`{ type: 'grid4', items: [{ index?: number, title: string, imgSrc?: string }] }`
      - 四宫格材料模块；`index` 手动序号；`title` 标题；`imgSrc` 图片。
    - `grid2`：`{ type: 'grid2', items: [{ type: 'image'|'list', src?: string, alt?: string, ordered?: boolean, items?: string[] }] }`
      - 两列混排；子项可为图片或列表。
    - `spec-box`：`{ type: 'spec-box', imageSrc: string, specs: { ... } }`
      - 中央主图 `imageSrc`；左右多栏规格卡 `specs.*.title/items`。
    - `callout`：`{ type: 'callout' | 'callout-warning' | 'callout-error', text: string, iconSrc?: string, className?: string }`
      - 警示/提示框；`iconSrc` 可替换默认图标。
    - `contents`：目录自动生成占位 `{ type: 'contents' }`
    - `steps`：步骤 `{ type: 'steps', items: string[] }`
    - `note`：注释 `{ type: 'note', style?: 'info'|'warning'|'success'|'error', text: string }`

示例：
```json
{
  "meta": {
    "title": "Vastera 使用说明书",
    "toc": [ { "title": "Cover", "page": 1 }, { "title": "Specification", "page": 9 } ]
  },
  "pages": [
    {
      "header": "Embrace the Revitalizing Chill",
      "blocks": [
        { "type": "heading", "text": "Embrace the Revitalizing Chill" },
        { "type": "paragraph", "text": "..." },
        { "type": "list", "items": ["...", "..."] },
        { "type": "image", "src": "/instruction_book/product.png", "fullWidth": false },
        { "type": "imageFloat-bottom-right", "src": "/instruction_book/cold.png" }
      ]
    }
  ]
}
```

## 导出能力
- 规格页：导出图片、PDF、可编辑 PDF
- 海报：导出图片、PDF
- 说明书：导出整本 PDF / 当前页可编辑式打印

## 常见问题
- 若静态资源路径无效，请确认图片文件是否存在于 `public/` 目录。
- 海报/说明书导出依赖 `html2canvas` 和 `jspdf`，跨域资源需允许 CORS。
