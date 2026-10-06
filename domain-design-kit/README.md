# Domain 設計工具包

用 Claude Code 跑 Domain 設計：AI 負責產出、自我挑錯；你負責提供資料、審查、做決定。不需要先讀任何規範文件，照下面的方式用就好。

---

## 1. 開一個新的設計 repo

把工具包資料夾**裡面的東西**複製到新 repo 的**最上層**（不是把 `domain-design-kit` 整個資料夾放進去，否則 Claude Code 讀不到規則）：

```bash
mkdir -p ~/projects/hr-domain-design
cp -r domain-design-kit/. ~/projects/hr-domain-design/    # 結尾的 /. 會連隱藏的 .claude/、.gitignore 一起複製
cd ~/projects/hr-domain-design
rm build_kit.py                                            # 只在研究資料夾使用
git init && git add . && git commit -m "Domain 設計工具包"
claude
```

複製完，新 repo 的最上層應該看得到 `CLAUDE.md`、`.claude/`、`docs/`、`templates/`。

## 2. 直接用說的開始

不用記指令，用一般的話告訴 AI 你想做什麼，說得很粗略也可以：

```
我們要做連鎖飲料店的人資系統
```

AI 會先問你幾個問題、去找資料，再和你一起整理出要分成哪幾段來做。你同意之後，說「開始做第一條」就行。

手上有需求說明、訪談紀錄、表單、規章的話，直接貼給 AI，或放進 `inputs/shared/`；沒有也沒關係。

## 3. 之後每次怎麼跟 AI 說

| 你想做的事 | 可以這樣說 |
|---|---|
| 不知道做到哪了 | 「現在做到哪？」 |
| 往下做 | 「繼續」「做下一步」 |
| 審查完了 | 「審查好了，可以凍結」 |
| 專家或客戶給了意見 | 「人資說其實要分開算」「專家回覆了：……」 |
| 想改切法、加情境 | 「這條要拆開」「多加一個加班的情境」 |
| 發現設計錯了 | 「這裡設計錯了」「上線後遇到一個特例」 |
| 想檢查有沒有漏 | 「檢查一下有沒有漏或衝突」 |

AI 每做完一步就會停下來等你，不會自己一路做下去。

每次開新的 Claude Code session，AI 會先從檔案整理出目前進度，不需要你重新交代。

## 4. 你要做的事

AI 會在需要你的時候停下來、告訴你要做什麼。整體來說是這些：

| 什麼時候 | 你要做的事 |
|---|---|
| 一開始 | 提供手上的資料；看 AI 寫的「推想草稿」，大致對就接受；同意要分成哪幾段、先做哪段 |
| 每一步做完 | 請**不是產出者**的人，照檔案最後的「檢查紀錄」逐條打勾，填上審查者、日期、結論 |
| AI 列出要問專家的問題時 | 找人資專家或客戶回答，把答案告訴 AI |
| 規則那一步 | 點開 AI 附的法規網址，確認原文沒抓錯 |
| 驗證時 | 自己（或請專家）先算好幾個案例的正確答案，AI 不能代算 |

## 5. 熟悉之後的捷徑（可選）

也可以直接打指令，效果和用說的一樣：`/domain-status`、`/domain-plan`、`/domain-new-slice`、`/domain-step`、`/domain-freeze`、`/domain-expert-reply`、`/domain-change`、`/domain-check`。

---

想了解背後的規則，可以看 `docs/`；但平常使用不需要讀。工具包的維護方式見 OntologyResearch 根目錄的 README。
