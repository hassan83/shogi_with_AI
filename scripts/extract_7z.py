"""7z アーカイブを py7zr で展開する（7z コマンドが無い環境用）。

shogi_setup.sh が評価関数（Háo）の展開に使う。
apt で p7zip-full が入らない環境（claude.ai の Code タブなど）では 7z コマンドが無いため、
代わりに pip で入る py7zr を使う。

使い方:  python3 extract_7z.py <アーカイブ.7z> <展開先ディレクトリ>
"""
import sys

import py7zr


def main():
    if len(sys.argv) != 3:
        print("usage: python3 extract_7z.py <archive.7z> <outdir>", file=sys.stderr)
        sys.exit(2)
    archive, outdir = sys.argv[1], sys.argv[2]
    with py7zr.SevenZipFile(archive, mode="r") as z:
        z.extractall(path=outdir)


if __name__ == "__main__":
    main()
