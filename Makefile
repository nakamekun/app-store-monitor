.PHONY: init seed-mock report daily-mock daily-real install-launchd uninstall-launchd logs test

PYTHON ?= python3
LAUNCHD_LABEL := io.github.app-store-monitor.daily
LAUNCHD_PLIST := $(HOME)/Library/LaunchAgents/$(LAUNCHD_LABEL).plist

init:
	$(PYTHON) -m src.cli init-db

seed-mock:
	$(PYTHON) -m src.cli seed-mock --days 14

report:
	$(PYTHON) -m src.cli report --print

daily-mock:
	$(PYTHON) -m src.cli daily --mock --print

daily-real:
	bash scripts/run_daily.sh

install-launchd:
	mkdir -p $(HOME)/Library/LaunchAgents logs
	cp config/launchd/$(LAUNCHD_LABEL).plist.example $(LAUNCHD_PLIST)
	launchctl unload $(LAUNCHD_PLIST) 2>/dev/null || true
	launchctl load $(LAUNCHD_PLIST)
	launchctl list | grep $(LAUNCHD_LABEL) || true

uninstall-launchd:
	launchctl unload $(LAUNCHD_PLIST) 2>/dev/null || true
	rm -f $(LAUNCHD_PLIST)

logs:
	mkdir -p logs
	ls -lah logs
	tail -n 120 logs/daily_$$(date +%F).log 2>/dev/null || true

test:
	$(PYTHON) -m unittest discover -s tests
