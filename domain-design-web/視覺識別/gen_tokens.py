import json, sys
C = [  # name, light, dark, usage —— 色調以簡報封面背景為基礎（天藍、長春花紫、淡紫、杏桃、玫瑰、白光）
("bg","#FFFFFF","#0A1224","頁面底色；上面再疊 glow-* 光暈（見 README「頁面背景」）。"),
("bg-soft","#F3F9FD","#111B32","側欄、次要區塊、輸入框底、結論橫條。取自封面最淡的霧藍。"),
("surface","#FFFFFF","#16213A","卡片、選項、抽屜的底（不透明）。"),
("surface-glass","#FFFFFFCC","#16213ACC","疊在光暈上的玻璃卡片（80% 不透明）；上面的字對比以 surface 計算。"),
("line","#DCE6F4","#27334E","卡片邊、表格線、分隔線（裝飾線，不承載意義）。"),
("line-strong","#8A94A8","#6B7894","輸入框與次要按鈕的邊（要看得出是控制項，3:1 以上）。"),
("ink","#0B1533","#E8EDF8","標題、正文；用在 bg、bg-soft、surface 與所有 *-soft 淡底上。"),
("ink-2","#55617A","#A3AEC6","次要正文、表格、說明小字；用在 bg、bg-soft、surface 上。"),
("muted","#7A8294","#8D98B2","18px 以上的導言；淺色主題只能放大字（3.9:1）。"),
("faint","#A0A8B4","#5C6782","頁碼、停用、裝飾性註記；不放要讀的字。"),
("accent","#3388F0","#6FB0FF","Lumori 藍（封面標題）：大字強調、圖示、進度、標題漸層起點；淺色主題不放 18px 以下的字。"),
("accent-strong","#1F64C8","#8CC0FF","連結、eyebrow、小字強調、焦點框；bg、surface、accent-soft 上 4.5:1 以上。"),
("accent-fill","#2470D8","#6FB0FF","主要按鈕的底。"),
("on-accent","#FFFFFF","#0B1533","放在 accent-fill 上的字與圖示。"),
("accent-soft","#E7F1FC","#15294A","膠囊、選中的導覽列、推薦選項的底；上面放 accent-strong 或 ink。"),
("accent-2","#98A8F0","#A9B6F5","長春花紫：標題漸層的終點；不單獨使用。"),
("sky-100","#E7F1FC","#13243F","封面色板：天藍 100（最淡）。"),
("sky-200","#D5E5F9","#1A2F52","封面色板：天藍 200。"),
("sky-300","#B8D7F8","#28466F","封面色板：天藍 300，光暈主色。"),
("sky-400","#A2C6F0","#3A5C8A","封面色板：天藍 400，封面最深的背景藍。"),
("periwinkle-200","#C2D2F0","#2A3766","封面色板：長春花紫。"),
("lavender-200","#CCC6F0","#342E5E","封面色板：淡紫（光束右側）。"),
("lavender-100","#DDDCEA","#252338","封面色板：灰紫（右下陰影）。"),
("apricot-200","#FCD8BA","#4A3322","封面色板：杏桃（光源旁的暖光）。"),
("apricot-100","#FCF0E4","#2C2119","封面色板：杏桃 100（暖白）。"),
("rose-200","#EACCC0","#43302C","封面色板：玫瑰（光源下方）。"),
("rose-100","#F6E4E4","#2E2024","封面色板：玫瑰 100。"),
("glow-blue","#B8D7F8","#1C3A66","頁面光暈（藍），只當裝飾。"),
("glow-lavender","#CCC6F0","#2E2A5A","頁面光暈（淡紫），只當裝飾。"),
("glow-peach","#FCD8BA","#3E2A1E","頁面光暈（杏桃），只當裝飾。"),
("ring-sky","#8CBEEF","#8CBEEF","字標 O 圓環的上半（藍）。取樣自簡報封面。"),
("ring-mist","#AED4EA","#AED4EA","字標 O 圓環的右側（淡青），藍與蜜桃之間的過渡。"),
("ring-peach","#F3C89A","#F3C89A","字標 O 圓環的下半（蜜桃）。"),
("wordmark-top","#23446E","#FFFFFF","字標 L U M R I 的上緣（鋼藍）；字母由上往下漸層。"),
("wordmark-mid","#071A37","#DCE6F5","字標字母 42% 高度處，漸層集中在上半。"),
("wordmark-bottom","#020517","#AFC0DB","字標字母的下緣（近黑）。"),
("ok","#2BB89A","#4FD6BD","完成、凍結、通過的圖形（✓ 圓、圓點）。封面沒有綠色，狀態色獨立於色板。"),
("ok-soft","#E8F7F2","#0F2E2A","完成狀態的淡底。"),
("ok-ink","#0F7A65","#4FD6BD","完成狀態的字；用在 ok-soft、surface 上。"),
("turn","#F0985A","#FFB27A","輪到你：圖形與圓點（杏桃加深）。"),
("turn-soft","#FDF0E4","#33221A","輪到你的淡底。"),
("turn-ink","#A84F14","#FFB27A","輪到你的字；用在 turn-soft、surface 上。"),
("hint","#D8B98A","#E8C08F","提示、支線的圖形。"),
("hint-soft","#FCF6EA","#2B2418","提示卡片的底（封面暖白）。"),
("hint-ink","#7E5118","#EBC896","提示的字；用在 hint-soft、surface 上。"),
("bad","#E86A78","#FF8A9A","錯誤、不通過、擋下的圖形（✕ 圓、⚠）。"),
("bad-soft","#FCEBEC","#351A22","錯誤卡片的底。"),
("bad-ink","#B3304A","#FF9AA8","錯誤的字；用在 bad-soft、surface 上。"),
("c1","#A2C6F0","#6FB0FF","① 範圍與驗收問題（天藍）：圖示與裝飾圖形；要讀的編號與字用 c1-ink。"),
("c1-soft","#E7F1FC","#132640","① 的淡底。"),
("c1-ink","#1F64C8","#8CC0FF","① 的編號與淡底上的小字。"),
("c2","#98A8F0","#9FB0FF","② 名詞盤點（長春花紫）：圖示與裝飾圖形；要讀的用 c2-ink。"),
("c2-soft","#ECEFFC","#1A2244","② 的淡底。"),
("c2-ink","#3A52C0","#B3C0FF","② 的編號與淡底上的小字。"),
("c3","#B4ACE8","#BDB2FF","③ 流程與狀態（淡紫）：圖示與裝飾圖形；要讀的用 c3-ink。"),
("c3-soft","#F1EFFB","#221D40","③ 的淡底。"),
("c3-ink","#5A45B5","#CBC1FF","③ 的編號與淡底上的小字。"),
("c4","#F5B98A","#FFB98A","④ 規則與限制（杏桃）：圖示與裝飾圖形；要讀的用 c4-ink。"),
("c4-soft","#FDF2E8","#33231A","④ 的淡底。"),
("c4-ink","#9A4E16","#FFC9A0","④ 的編號與淡底上的小字。"),
("c5","#E2AFA6","#F0B4AA","⑤ 投影到實作（玫瑰）：圖示與裝飾圖形；要讀的用 c5-ink。"),
("c5-soft","#FBEDEA","#36201F","⑤ 的淡底。"),
("c5-ink","#9C3F36","#F7C2B9","⑤ 的編號與淡底上的小字。"),
("c6","#6F8DBE","#8FAEDF","⑥ 跑起來驗證（鋼藍，取自字標）：圖示與裝飾圖形；要讀的用 c6-ink。"),
("c6-soft","#EAF0F8","#17243A","⑥ 的淡底。"),
("c6-ink","#2F4E7E","#A9C2EA","⑥ 的編號與淡底上的小字。"),
]
def L(h):
    h=h.lstrip('#')[:6]; r,g,b=[int(h[i:i+2],16)/255 for i in (0,2,4)]
    f=lambda c: c/12.92 if c<=0.03928 else ((c+0.055)/1.055)**2.4
    return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b)
def cr(a,b):
    x,y=sorted([L(a),L(b)],reverse=True); return (x+.05)/(y+.05)
d={n:(l,k) for n,l,k,_ in C}
checks=[("ink","bg"),("ink","bg-soft"),("ink-2","bg"),("ink-2","bg-soft"),("ink-2","surface"),("accent-strong","bg"),("accent-strong","bg-soft"),("accent-strong","accent-soft"),("on-accent","accent-fill"),("line-strong","bg"),("ok-ink","ok-soft"),("turn-ink","turn-soft"),("hint-ink","hint-soft"),("bad-ink","bad-soft"),("muted","bg")]
checks+= [(f"c{i}-ink",f"c{i}-soft") for i in range(1,7)] + [(f"c{i}","surface") for i in range(1,7)] + [("ink",f"c{i}-soft") for i in range(1,7)]
for a,b in checks:
    print(f"{a:14} on {b:12} light {cr(d[a][0],d[b][0]):5.2f}  dark {cr(d[a][1],d[b][1]):5.2f}")
tokens={"name":"Lumori","version":1,
 "color":{"themes":[{"id":"light","name":"淺色"},{"id":"dark","name":"深色"}],
  "tokens":[{"name":n,"value":{"light":l.lower(),"dark":k.lower()},"usage":u} for n,l,k,u in C]},
 "type":{"fonts":[],
  "families":{"sans":"Manrope, \"Noto Sans TC\", system-ui, sans-serif","mono":"ui-monospace, \"SF Mono\", Menlo, Consolas, monospace"},
  "groups":[
   {"name":"標題","family":"sans","styles":[
    {"name":"display","fontSize":"40px","lineHeight":1.25,"fontWeight":900,"letterSpacing":"0","sample":"一個人，不等於一個員工","usage":"首頁與步驟頁的大標，一頁一個。"},
    {"name":"h1","fontSize":"28px","lineHeight":1.3,"fontWeight":900,"sample":"hire-employee 第 ② 步","usage":"頁面標題。"},
    {"name":"h2","fontSize":"22px","lineHeight":1.35,"fontWeight":700,"sample":"要你回答的問題","usage":"區塊標題。"},
    {"name":"h3","fontSize":"17px","lineHeight":1.4,"fontWeight":700,"sample":"Employment 要不要獨立成一個東西","usage":"卡片標題、選項標題。"}]},
   {"name":"內文","family":"sans","styles":[
    {"name":"lead","fontSize":"18px","lineHeight":1.7,"fontWeight":400,"sample":"同一個人可以有好幾段雇用關係。","usage":"標題下的一段說明，用 muted 或 ink-2。"},
    {"name":"body","fontSize":"16px","lineHeight":1.75,"fontWeight":400,"sample":"離職後再回公司，前後是兩段不同的雇用關係。","usage":"正文。"},
    {"name":"small","fontSize":"14px","lineHeight":1.6,"fontWeight":400,"sample":"依據：勞動基準法第 38 條（特別休假）","usage":"表格、說明、依據。"}]},
   {"name":"標籤","family":"sans","styles":[
    {"name":"eyebrow","fontSize":"13px","lineHeight":1.4,"fontWeight":700,"letterSpacing":"0.08em","sample":"02　名詞盤點","usage":"標題上方的步驟編號與名稱，用 accent-strong。"},
    {"name":"overline","fontSize":"12px","lineHeight":1.5,"fontWeight":500,"letterSpacing":"0.2em","sample":"FROM REALITY TO A SHARED MEANING","usage":"全大寫英文註記、頁碼，用 faint；不放要讀的內容。"},
    {"name":"wordmark","fontSize":"20px","lineHeight":1,"fontWeight":600,"letterSpacing":"0.35em","sample":"LUMORI","usage":"頂列字標，全大寫。"}]},
   {"name":"程式","family":"mono","styles":[
    {"name":"code","fontSize":"13px","lineHeight":1.6,"fontWeight":400,"sample":"slices/hire-employee/02_entities.md","usage":"檔名、指令、編號（D-12、R04）。"}]}]},
 "spacing":{"tokens":[{"name":f"space-{k}","value":f"{v}px","usage":u} for k,v,u in [
   (1,4,"圖示和字之間。"),(2,8,"膠囊內距、緊密列表。"),(3,12,"按鈕內元素間距、表格內距。"),(4,16,"卡片之間、手機邊界。"),
   (6,24,"卡片內距、段落之間。"),(8,32,"區塊內大段落。"),(12,48,"標題區到內容。"),(16,64,"頁面區塊之間。")]]},
 "radius":{"tokens":[
   {"name":"radius-sm","value":"8px","usage":"膠囊以外的小元件：導覽列、標籤、程式碼。"},
   {"name":"radius-md","value":"12px","usage":"按鈕、輸入框。"},
   {"name":"radius-lg","value":"16px","usage":"卡片、選項、結論橫條。"},
   {"name":"radius-xl","value":"24px","usage":"抽屜、對話框、首頁大卡片。"},
   {"name":"radius-pill","value":"999px","usage":"膠囊、狀態圓、圖示圓。"}]},
 "shadow":{"tokens":[
   {"name":"shadow-card","value":{"light":"0 1px 2px rgba(11,21,51,0.04), 0 8px 24px rgba(11,21,51,0.06)","dark":"0 1px 2px rgba(0,0,0,0.30), 0 8px 24px rgba(0,0,0,0.35)"},"usage":"卡片、選項。"},
   {"name":"shadow-pop","value":{"light":"0 12px 40px rgba(11,21,51,0.14)","dark":"0 12px 40px rgba(0,0,0,0.55)"},"usage":"抽屜、對話框、提示訊息。"},
   {"name":"shadow-btn","value":{"light":"0 1px 2px rgba(11,21,51,0.08), 0 4px 12px rgba(36,112,216,0.22)","dark":"0 1px 2px rgba(0,0,0,0.4), 0 4px 12px rgba(0,0,0,0.4)"},"usage":"主要按鈕。"}]}}
json.dump(tokens,open(sys.argv[1],'w'),ensure_ascii=False,indent=1)
