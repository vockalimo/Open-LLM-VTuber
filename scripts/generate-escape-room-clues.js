/**
 * generate-escape-room-clues.js — 用 Codex CLI 生成密室逃脫線索圖
 *
 * 使用方式:
 *   node scripts/generate-escape-room-clues.js
 *   node scripts/generate-escape-room-clues.js --dry-run   # 只印 prompt 不生圖
 *
 * 輸出:
 *   game_assets/escape/clue-whiteboard.jpg
 *   game_assets/escape/clue-intercom.jpg
 *   game_assets/escape/clue-access-log.jpg
 *   game_assets/escape/clue-door-open.jpg
 */

import { execSync, spawnSync } from 'child_process'
import { writeFileSync, mkdirSync, existsSync, readdirSync, statSync, copyFileSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'
import { homedir, tmpdir } from 'os'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT_DIR  = join(__dirname, '..')
const OUT_DIR   = join(ROOT_DIR, 'game_assets', 'escape')
const DRY_RUN      = process.argv.includes('--dry-run')
const OVERLAY_ONLY = process.argv.includes('--overlay-only')  // 只重跑 overlay，不重新生圖

// ── 4 張線索圖的 prompt ────────────────────────────────────────
// 注意：prompt 全用英文（AI 畫中文字會亂碼），中文字由 Python 後製疊加
const CLUES = [
  {
    file: 'clue-whiteboard.jpg',
    prompt: `A close-up photograph of a large whiteboard in a security control room.
The whiteboard surface is clean white with some dust marks and eraser smudges.
There are faint grid lines and a small "TODAY'S CODE" label at the bottom showing only "4 _ _ 2".
The rest of the whiteboard has some incomplete handwritten notes that are too faint to read.
Fluorescent office lighting, slightly dramatic security room atmosphere.
Leave plenty of blank writing space in the CENTER and UPPER area of the whiteboard for text to be added.
No Chinese characters. No people visible. 4:3 aspect ratio.`,
    // 後製疊加的中文文字
    overlay: {
      type: 'whiteboard',
      lines: [
        '緊急封鎖覆寫碼 — 值班計算規則',
        '',
        '位置 1：本日固定碼（見底部）',
        '位置 2：當班保全工號',
        '位置 3：最近一次異常刷卡的「小時數」',
        '位置 4：本日固定碼（見底部）',
        '',
        '本日固定碼：4 _ _ 2',
        '（位置 2、3 停電後遺失，請現場確認）',
      ],
    },
  },
  {
    file: 'clue-intercom.jpg',
    prompt: `A wall-mounted security intercom panel in a dimly lit security control room.
The intercom has a glowing green "CONNECTED" indicator light, a speak button, and a small speaker grille.
A small blank label plate is mounted below the intercom.
A white speech bubble shape floats to the right of the intercom, currently empty.
Style: realistic photograph, slightly dramatic blue-green security lighting.
No Chinese characters. No people visible. 4:3 aspect ratio.`,
    overlay: {
      type: 'speech_bubble',
      lines: [
        '我是今天的值班保全，',
        '工號 3 號。',
        '有什麼需要嗎？',
      ],
    },
  },
  {
    file: 'clue-access-log.jpg',
    prompt: `A close-up of a printed access log sheet on a clipboard placed on a desk in a security room.
The paper shows a table with 4 columns. Most rows are blank or contain faint illegible text.
The LAST row at the bottom is highlighted with a red rectangle but contains no text yet.
Above the table is a blank header area.
Style: realistic photograph under fluorescent light, slight paper texture visible.
No Chinese characters. 4:3 aspect ratio.`,
    overlay: {
      type: 'table',
      header: '門禁刷卡紀錄 — 今日',
      columns: ['時間', '刷卡人員', '門號', '狀態'],
      rows: [
        ['08:02', '員工 A', 'G-001', '正常'],
        ['09:14', '員工 B', 'G-001', '正常'],
        ['12:33', '員工 C', 'G-002', '正常'],
        ['18:50', '員工 A', 'G-001', '正常'],
        ['凌晨 01:47', 'X-047', 'G-003', '警示：非授權時段'],
      ],
      highlightLast: true,
      note: '★ 異常刷卡發生在凌晨 1 時 47 分（小時數 = 1）',
    },
  },
  {
    file: 'clue-door-open.jpg',
    prompt: `A heavy metal security door in a control room slowly swinging open.
Warm golden light streams through the crack of the open door.
A digital keypad on the wall to the right of the door shows green LED lights glowing, buttons labeled 0-9.
The display screen of the keypad shows "4312" and green indicator light is ON.
Style: dramatic cinematic photograph, slightly dark control room with hopeful golden light from the doorway.
No Chinese characters. No people visible. 4:3 aspect ratio.`,
    overlay: {
      type: 'keypad_label',
      lines: ['已解鎖', 'UNLOCKED'],
    },
  },
]

// ── 找 codex 生成的最新圖片 ──────────────────────────────────
function findLatestGeneratedImage(afterTime, workDir) {
  let newest = null
  let newestTime = afterTime || 0

  // 先找 workDir
  if (workDir && existsSync(workDir)) {
    for (const file of readdirSync(workDir)) {
      if (!/\.(png|jpg|jpeg|webp)$/i.test(file)) continue
      const fp = join(workDir, file)
      const mtime = statSync(fp).mtimeMs
      if (mtime > newestTime) { newestTime = mtime; newest = fp }
    }
    if (newest) return newest
  }

  // fallback: ~/.codex/generated_images/
  const base = join(homedir(), '.codex', 'generated_images')
  if (!existsSync(base)) return null
  for (const folder of readdirSync(base)) {
    const folderPath = join(base, folder)
    try {
      if (!statSync(folderPath).isDirectory()) continue
      for (const file of readdirSync(folderPath)) {
        if (!/\.(png|jpg|jpeg|webp)$/i.test(file)) continue
        const fp = join(folderPath, file)
        const mtime = statSync(fp).mtimeMs
        if (mtime > newestTime) { newestTime = mtime; newest = fp }
      }
    } catch { /* 略過 */ }
  }
  return newest
}

function generateImage(prompt, outputPath) {
  const workDir = join(tmpdir(), `escape-clue-${Date.now()}`)
  mkdirSync(workDir, { recursive: true })

  const promptFile = join(workDir, '_prompt.txt')
  // codex prompt：只要求生成圖片，不加任何中文
  const codexPrompt = `Please generate an image using the image_gen tool with this description:

${prompt}

After generating, save the image as "output.png" in the current working directory using Python. Just generate once and save it.`
  writeFileSync(promptFile, codexPrompt, 'utf8')

  const beforeTime = Date.now()
  const codexArgs = [
    'exec',
    '-s', 'danger-full-access',
    '--dangerously-bypass-approvals-and-sandbox',
    '-m', 'gpt-5.4',
    '-C', workDir,
  ]

  try {
    execSync(`codex ${codexArgs.join(' ')} < "${promptFile}"`, {
      cwd: workDir,
      encoding: 'utf8',
      timeout: 300000,
      maxBuffer: 20 * 1024 * 1024,
      shell: true,
    })
  } catch (e) {
    if (e.code === 'ETIMEDOUT') throw new Error('codex 執行逾時')
    throw new Error(`codex 執行失敗: ${e.message}`)
  }

  const generated = findLatestGeneratedImage(beforeTime, workDir)
  if (!generated) throw new Error('找不到 codex 生成的圖片')

  copyFileSync(generated, outputPath)
}

// ── 後製：用 Python Pillow 疊加中文文字 ──────────────────────
const OVERLAY_PYTHON = `
import sys, json
from PIL import Image, ImageDraw, ImageFont

image_path = sys.argv[1]
overlay_data = json.loads(sys.argv[2])

FONT_PATH = '/System/Library/Fonts/STHeiti Medium.ttc'

def load_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except:
        return ImageFont.load_default()

img = Image.open(image_path).convert('RGBA')
W, H = img.size
t = overlay_data['type']

draw_layer = Image.new('RGBA', (W, H), (0,0,0,0))
draw = ImageDraw.Draw(draw_layer)

if t == 'whiteboard':
    lines = overlay_data['lines']
    pad = 20
    line_h = 38
    block_h = len(lines) * line_h + pad * 2
    block_w = int(W * 0.78)
    x0 = int(W * 0.11)
    y0 = int(H * 0.08)
    draw.rounded_rectangle([x0-pad, y0-pad, x0+block_w, y0+block_h], radius=8, fill=(255,255,255,210))
    for i, line in enumerate(lines):
        if not line:
            continue
        font_size = 28 if i == 0 else 24
        font = load_font(font_size)
        color = (30, 30, 30, 255) if i == 0 else (60, 60, 60, 255)
        draw.text((x0, y0 + i * line_h), line, font=font, fill=color)

elif t == 'speech_bubble':
    lines = overlay_data['lines']
    font = load_font(30)
    pad = 20
    line_h = 42
    max_w = max(draw.textlength(l, font=font) for l in lines if l)
    bw = int(max_w) + pad * 2
    bh = len(lines) * line_h + pad * 2
    bx = int(W * 0.42)
    by = int(H * 0.25)
    draw.rounded_rectangle([bx, by, bx+bw, by+bh], radius=14, fill=(255,255,255,230), outline=(100,100,100,200), width=2)
    tail = [(bx, by+bh//2-10), (bx-18, by+bh//2), (bx, by+bh//2+10)]
    draw.polygon(tail, fill=(255,255,255,230))
    for i, line in enumerate(lines):
        draw.text((bx+pad, by+pad+i*line_h), line, font=font, fill=(30,30,30,255))

elif t == 'table':
    header = overlay_data.get('header','')
    columns = overlay_data['columns']
    rows = overlay_data['rows']
    highlight_last = overlay_data.get('highlightLast', False)
    note = overlay_data.get('note', '')
    font_h = load_font(26)
    font_b = load_font(22)
    font_s = load_font(20)
    # 時間欄加寬（第 0 欄），其餘平分剩餘空間
    table_w = int(W * 0.82)
    col0_w  = 160  # 時間欄固定較寬
    rest_w  = (table_w - col0_w) // (len(columns) - 1)
    col_widths = [col0_w] + [rest_w] * (len(columns) - 1)
    row_h = 40
    pad = 14
    tx = int(W * 0.09)
    ty = int(H * 0.08)
    total_h = row_h * (len(rows) + 2) + pad * 2 + (40 if note else 0)
    draw.rounded_rectangle([tx-pad, ty-pad, tx+table_w+pad, ty+total_h], radius=8, fill=(255,255,255,218))
    draw.text((tx, ty), header, font=font_h, fill=(30,30,100,255))
    ty += 44
    # 欄位標題
    cx = tx
    for ci, col in enumerate(columns):
        draw.text((cx + 4, ty), col, font=font_b, fill=(80,80,80,255))
        cx += col_widths[ci]
    ty += row_h
    draw.line([(tx, ty), (tx+table_w, ty)], fill=(150,150,150,200), width=1)
    for ri, row in enumerate(rows):
        is_last = (ri == len(rows)-1)
        if is_last and highlight_last:
            draw.rectangle([tx-4, ty+1, tx+table_w+4, ty+row_h-1], fill=(255,60,60,90))
        color = (180,0,0,255) if is_last and highlight_last else (50,50,50,255)
        cx = tx
        for ci, cell in enumerate(row):
            draw.text((cx + 4, ty+8), cell, font=font_s, fill=color)
            cx += col_widths[ci]
        ty += row_h
    # 底部附注（突顯謎題關鍵資訊）
    if note:
        ty += 6
        draw.rounded_rectangle([tx, ty, tx+table_w, ty+32], radius=6, fill=(255,200,0,200))
        draw.text((tx+8, ty+5), note, font=load_font(19), fill=(80,30,0,255))

elif t == 'keypad_label':
    lines = overlay_data['lines']
    font = load_font(36)
    bx = int(W * 0.62)
    by = int(H * 0.25)
    pad = 16
    line_h = 48
    bw = 200
    bh = len(lines) * line_h + pad * 2
    draw.rounded_rectangle([bx, by, bx+bw, by+bh], radius=10, fill=(0,180,0,200))
    for i, line in enumerate(lines):
        draw.text((bx+pad, by+pad+i*line_h), line, font=font, fill=(255,255,255,255))

merged = Image.alpha_composite(img, draw_layer).convert('RGB')
merged.save(image_path, quality=92)
print('OK')
`

function overlayChineseText(imagePath, overlay) {
  const result = spawnSync('python3', ['-c', OVERLAY_PYTHON, imagePath, JSON.stringify(overlay)], { encoding: 'utf8' })
  if (result.error || result.status !== 0) {
    console.warn(`   ⚠️  文字疊加失敗: ${result.stderr?.slice(-200) || result.error?.message}`)
  } else {
    console.log(`   🈶 中文字疊加完成`)
  }
}

function main() {
  console.log('\n🔍 密室逃脫線索圖生成器')
  console.log(`📁 輸出目錄: ${OUT_DIR}\n`)
  mkdirSync(OUT_DIR, { recursive: true })

  for (const clue of CLUES) {
    const outputPath = join(OUT_DIR, clue.file)
    console.log(`🖼️  生成: ${clue.file}`)

    if (DRY_RUN) {
      console.log(`   📝 Prompt 預覽:\n   ${clue.prompt.slice(0, 120)}...\n`)
      continue
    }

    try {
      const basePath = outputPath.replace(/(\.\w+)$/, '_base$1')

      if (OVERLAY_ONLY) {
        // --overlay-only：直接從底圖備份重疊加，不重新生圖
        if (!existsSync(basePath)) throw new Error(`找不到底圖備份 ${basePath}，請先完整執行一次`)
        copyFileSync(basePath, outputPath)
        console.log(`   ♻️  使用底圖備份`)
      } else {
        generateImage(clue.prompt, outputPath)
        // 存一份乾淨底圖備份（供 --overlay-only 使用）
        copyFileSync(outputPath, basePath)
        console.log(`   ✅ 儲存: ${outputPath}`)
      }

      // 後製：疊加中文文字
      if (clue.overlay) {
        overlayChineseText(outputPath, clue.overlay)
      }
    } catch (e) {
      console.error(`   ❌ 失敗: ${e.message}`)
    }
  }

  if (!DRY_RUN) {
    console.log('\n🎉 全部完成！')
    console.log('   線索圖位於 game_assets/escape/')
    console.log('   URL 路徑：/game/escape/clue-*.jpg')
  }
}

main()
