.PHONY: all flash clean test

all:
	$(MAKE) -C firmware all

flash:
	$(MAKE) -C firmware flash

clean:
	$(MAKE) -C firmware clean

test:
	python3 -m pytest tests/ -v
