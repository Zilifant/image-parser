.PHONY: setup dev test download-sam

setup:
	cd backend && uv sync
	cd frontend && npm install

dev:
	./scripts/dev.sh

test:
	cd backend && uv run pytest

# MobileSAM checkpoint (~40MB) enables the optional SAM point/box tools.
# Also run `cd backend && uv sync --extra sam` to install torch + mobile-sam.
download-sam:
	mkdir -p backend/models
	curl -L -o backend/models/mobile_sam.pt \
		https://github.com/ChaoningZhang/MobileSAM/raw/master/weights/mobile_sam.pt
