# D2-RGB-Tool

Exception in thread Thread-3 (fetch_data):
Traceback (most recent call last):
  File "C:\Users\louis\AppData\Local\Programs\Python\Python311\Lib\threading.py", line 1038, in _bootstrap_inner
    self.run()
  File "C:\Users\louis\AppData\Local\Programs\Python\Python311\Lib\threading.py", line 975, in run
    self._target(*self._args, **self._kwargs)
  File "c:\Users\louis\Documents\D2 RGB Tool\src\main.py", line 159, in fetch_data
    subclass_name, equipped_super = self.get_subclass_and_super(equipped_subclass)
                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "c:\Users\louis\Documents\D2 RGB Tool\src\main.py", line 172, in get_subclass_and_super
    subclass_supers = get_subclass_hashes()
                      ^^^^^^^^^^^^^^^^^^^^^
  File "c:\Users\louis\Documents\D2 RGB Tool\src\main.py", line 49, in get_subclass_hashes
    subclass_supers[item["hash"]] = {"subclass_name": subclass_name, "supers": super_abilities}
                    ~~~~^^^^^^^^
KeyError: 'hash'