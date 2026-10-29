
C:\Users\Hossein\Desktop\New folder>python import_rialnerkh.py
             USD -> currency:usd                  2895 نقطه‌ی خام،  862 اضافه شد
             EUR -> currency:eur                  2895 نقطه‌ی خام،  862 اضافه شد
             GBP -> currency:gbp                  2895 نقطه‌ی خام،  862 اضافه شد
             TRY -> currency:try                  2894 نقطه‌ی خام،  862 اضافه شد
Traceback (most recent call last):
  File "C:\Users\Hossein\Desktop\New folder\import_rialnerkh.py", line 145, in <module>
    main()
    ~~~~^^
  File "C:\Users\Hossein\Desktop\New folder\import_rialnerkh.py", line 126, in main
    pts = parse_rows(fetch_json(code, args.days))
                     ~~~~~~~~~~^^^^^^^^^^^^^^^^^
  File "C:\Users\Hossein\Desktop\New folder\import_rialnerkh.py", line 45, in fetch_json
    return json.loads(r.read().decode("utf-8"))
                      ~~~~~~^^
  File "C:\Users\Hossein\AppData\Local\Programs\Python\Python314\Lib\http\client.py", line 488, in read
    return self._read_chunked(amt)
           ~~~~~~~~~~~~~~~~~~^^^^^
  File "C:\Users\Hossein\AppData\Local\Programs\Python\Python314\Lib\http\client.py", line 627, in _read_chunked
    value.append(self._safe_read(chunk_left))
                 ~~~~~~~~~~~~~~~^^^^^^^^^^^^
  File "C:\Users\Hossein\AppData\Local\Programs\Python\Python314\Lib\http\client.py", line 667, in _safe_read
    data = self.fp.read(cursize)
  File "C:\Users\Hossein\AppData\Local\Programs\Python\Python314\Lib\socket.py", line 729, in readinto
    return self._sock.recv_into(b)
           ~~~~~~~~~~~~~~~~~~~~^^^
  File "C:\Users\Hossein\AppData\Local\Programs\Python\Python314\Lib\ssl.py", line 1304, in recv_into
    return self.read(nbytes, buffer)
           ~~~~~~~~~^^^^^^^^^^^^^^^^
  File "C:\Users\Hossein\AppData\Local\Programs\Python\Python314\Lib\ssl.py", line 1138, in read
    return self._sslobj.read(len, buffer)
           ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^
ssl.SSLError: [SSL: RECORD_LAYER_FAILURE] record layer failure (_ssl.c:2713)
