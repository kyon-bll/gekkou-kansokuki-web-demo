#!/usr/bin/env python3
"""Optional short Chromium smoke check for the revised tutorial.

The game does not require Python, Playwright, or a build. These are development
checks only. With --url, open the real deployment. Otherwise load the unchanged
HTML via set_content; that mode does NOT validate URL delivery or file:// loading.
Dialogue is fast-forwarded, not played at a human reading pace.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', help='Actual file/local/deployment URL to validate')
    parser.add_argument('--browser', help='Existing Chromium executable path')
    parser.add_argument('--screenshots', type=Path, help='Optional small set of screenshots')
    args = parser.parse_args()
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
    errors, console_errors, requests, checks = [], [], [], []
    with sync_playwright() as p:
        options = {'headless': True, 'args': ['--no-sandbox']}
        if args.browser:
            options['executable_path'] = args.browser
        browser = p.chromium.launch(**options)
        page = browser.new_page(viewport={'width': 1365, 'height': 900})
        page.set_default_timeout(5000)
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: console_errors.append(m.text) if m.type == 'error' else None)
        page.on('request', lambda r: requests.append(r.url))
        if args.url:
            page.goto(args.url, wait_until='load')
        else:
            page.set_content((ROOT/'index.html').read_text(encoding='utf-8'), wait_until='load')

        def advance() -> None:
            for _ in range(30):
                if page.locator('#dialogue').is_hidden():
                    return
                page.locator('#dialogue-next').click()
            raise AssertionError('Dialogue did not end within 30 clicks')

        def close() -> None:
            page.locator('#modal-close').click()

        def capture(name: str) -> None:
            if args.screenshots:
                page.screenshot(path=str(args.screenshots/f'{name}.png'))

        def shelf() -> None:
            page.locator('#hotspot-shelf').click()
            advance()

        def room() -> None:
            page.locator('#leave-shelf').click()

        def pick() -> None:
            page.locator('#pick-book').click()

        page.locator('#start-game').click()
        first_line=page.locator('#dialogue-text').inner_text()
        page.locator('#open-help').click()
        page.keyboard.press('Space')
        assert page.locator('#dialogue-text').inner_text()==first_line
        page.keyboard.press('Escape')
        page.locator('#dialogue-next').focus()
        page.keyboard.press('Enter')
        expect(page.locator('#dialogue-text')).to_contain_text('今日は、その本を片づけに来た。')
        advance()
        for target in ['hotspot-mantis','hotspot-path','hotspot-gate-door','hotspot-gate-door']:
            page.locator('#'+target).click(); advance()
        assert page.locator('#hotspot-man').count()==0
        assert page.locator('#scene-art [data-pugyu]').count()==0
        assert page.locator('#hotspot-paper').count()==0
        checks.append('Title → ADV → mantis → empty warehouse → library; keyboard and modal controls')

        # Rescuing uses the normal book-pick operation, before any companion permission.
        page.locator('#hotspot-floor').click(); pick(); capture('00-rescue-dialogue'); advance()
        expect(page.locator('#hotspot-pugyu')).to_be_visible()
        expect(page.locator('#hotspot-paper')).to_be_visible()
        assert page.locator('#scene-art [data-pugyu]').count()==1
        page.locator('#hotspot-pugyu').click()
        expect(page.locator('#modal-body')).to_contain_text('足元の紙、読んだか？')
        close()
        # A replaced floor book must not hide the exposed paper or repeat the rescue.
        page.locator('#hotspot-floor').click()
        page.locator('#place-actions').get_by_role('button',name='選択中の本を置く',exact=True).click()
        expect(page.locator('#hotspot-paper')).to_be_visible()
        page.locator('#hotspot-floor').click(); pick()
        expect(page.locator('#dialogue')).to_be_hidden()
        capture('01-rescue')
        page.locator('#open-notes').click()
        assert page.locator('#modal-body .chart-table').count()==0
        close()
        page.locator('#hotspot-paper').click()
        expect(page.locator('#modal-body .chart-table')).to_contain_text('エイボンの書')
        close()
        assert page.locator('#hotspot-paper').count()==0
        checks.append('One-time rescue, explicit paper discovery, paper stays exposed after floor placement')

        shelf()
        expect(page.locator('#chart-panel')).to_be_visible()
        expect(page.locator('[data-book="demon"]')).to_have_attribute('aria-pressed','true')
        page.locator('#toggle-chart').click()
        expect(page.locator('#chart-panel')).to_be_hidden()
        page.locator('#toggle-chart').click()
        expect(page.locator('[data-book="demon"]')).to_have_attribute('aria-pressed','true')
        page.locator('#read-plaque').click()
        expect(page.locator('.plaque')).to_have_text('窓辺の棚')
        close()
        # Occupied placement must leave both books untouched and preserve the selection.
        page.locator('[data-slot="1"]').click()
        expect(page.locator('#modal-title')).to_contain_text('エイボンの書')
        close()
        expect(page.locator('[data-book="demon"]')).to_have_attribute('aria-pressed','true')
        page.locator('[data-slot="3"]').click()  # deliberate mis-shelving
        expect(page.locator('[data-slot="3"]')).to_contain_text('悪魔信仰')
        expect(page.locator('#dialogue')).to_be_hidden()
        expect(page.locator('#shelf-diary')).to_be_hidden()
        checks.append('Reference panel stays usable; selection preserved; occupied-slot protection and wrong shelving')

        page.locator('[data-slot="1"]').click(); pick()
        page.locator('#put-side').click()
        expect(page.locator('#put-side small')).to_contain_text('1冊')
        page.locator('[data-slot="3"]').click(); pick()
        page.locator('[data-slot="0"]').click()
        page.locator('#put-side').click()
        page.locator('[data-open-book="eibon"]').click(); pick()
        page.locator('[data-slot="3"]').click()
        room()
        page.locator('#hotspot-desk').click()
        page.locator('[data-open-book="stars"]').click()
        page.get_by_role('button',name='開いて読む',exact=True).click()
        expect(page.locator('#book-pages')).to_contain_text('夜空の図')
        pick(); shelf(); page.locator('[data-slot="1"]').click()
        room()
        page.locator('#hotspot-desk').click(); pick()
        shelf()
        capture('02-reference-shelf')
        # Additional viewports only inspect this state; no repeated full walkthrough.
        for width,height in [(1365,768),(390,844)]:
            page.set_viewport_size({'width':width,'height':height})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), f'horizontal overflow: {width}'
            expect(page.locator('#toggle-chart')).to_be_visible()
            expect(page.locator('#chart-panel')).to_be_visible()
        page.set_viewport_size({'width':1365,'height':900})
        page.locator('[data-slot="2"]').click()  # last placement; no grading button
        expect(page.locator('#dialogue')).to_be_visible()
        expect(page.locator('#shelf-sigil')).to_be_visible()
        assert page.locator('.shelf-slot.occupied').count()==4
        advance()
        expect(page.locator('#shelf-diary')).to_be_visible()
        expect(page.locator('#end-screen')).to_be_hidden()
        checks.append('Floor/side recovery; shelving activates automatically without reading all books; small viewport checks')

        page.locator('#shelf-diary').click()
        expect(page.locator('#diary-pages')).to_be_hidden()
        close()
        expect(page.locator('#end-screen')).to_be_hidden()
        expect(page.locator('#dialogue')).to_be_hidden()
        page.locator('#shelf-diary').click()
        page.locator('#read-diary').click()
        expect(page.locator('#diary-pages p')).to_have_text(page.evaluate('GAME_DATA.diary.page'))
        expect(page.locator('#end-screen')).to_be_hidden()
        capture('03-first-diary-page')
        page.locator('#diary-close').click()
        expect(page.locator('#dialogue-text')).to_have_text('この字……おじさんのだ。')
        advance()
        expect(page.locator('#end-screen')).to_be_visible()
        capture('04-ending')
        checks.append('Reward can be closed unopened, reopened, read at own pace, then reflection → ending')

        page.locator('#explore-after-end').click()
        expect(page.locator('#objective')).to_contain_text('デモ終了')
        page.locator('#open-notes').click()
        expect(page.locator('#modal-body .chart-table')).to_be_visible()
        expect(page.locator('#modal-body')).to_contain_text(page.evaluate('GAME_DATA.diary.page'))
        close()
        page.locator('[data-slot="0"]').click(); pick()
        page.locator('#put-floor').click()
        expect(page.locator('#shelf-diary')).to_be_visible()
        page.locator('#put-floor').click()
        page.locator('[data-open-book="demon"]').click(); pick()
        page.locator('[data-slot="0"]').click()
        expect(page.locator('#dialogue')).to_be_hidden()
        assert 'reacting' not in (page.locator('#shelf-sigil').get_attribute('class') or '')
        page.locator('#open-backlog').click()
        lines=page.locator('.backlog-item p').all_text_contents()
        assert lines.count('助かったぜ')==1
        assert lines.count('今、棚の奥が動いたぞ。')==1
        close()
        page.locator('#shelf-diary').click()
        expect(page.locator('#diary-pages')).to_be_visible()
        close()
        expect(page.locator('#dialogue')).to_be_hidden()
        checks.append('Notebook reread; one rescue/reaction only; moving books after completion keeps the reward')

        page.locator('#back-title').click()
        page.locator('#title-confirm').get_by_role('button',name='表紙に戻る',exact=True).click()
        page.locator('#start-game').click(); advance()
        expect(page.locator('#hotspot-mantis')).to_be_visible()
        expect(page.locator('#toggle-chart')).to_be_hidden()
        expect(page.locator('#shelf-diary')).to_be_hidden()
        assert page.locator('.inventory-book').count()==0
        checks.append('Reset clears inventory, reference panel, and reward')
        assert not errors, errors
        assert not console_errors, console_errors
        if not args.url:
            assert not requests, requests
        result={
            'status':'passed','version':page.evaluate('GAME_DATA.version'),
            'browser':browser.version,'mode':args.url or 'unchanged index.html via page.set_content',
            'checks':checks,'page_errors':errors,'console_errors':console_errors,
            'network_requests':requests,
            'not_verified':['GitHub Pages deployment','Safari/Firefox','human playtime and narrative pacing']+([] if args.url else ['file:// navigation','HTTP URL delivery'])
        }
        print(json.dumps(result,ensure_ascii=False,indent=2))
        if args.screenshots:
            (args.screenshots/'smoke-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        browser.close()

if __name__=='__main__':
    main()
