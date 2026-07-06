from unittest.mock import patch, MagicMock
from pathlib import Path
from src.core.ollama_installer import OllamaInstaller

def test_detect_platform():
    with patch("sys.platform", "win32"):
        assert OllamaInstaller.detect_platform() == "windows"
    with patch("sys.platform", "darwin"):
        assert OllamaInstaller.detect_platform() == "darwin"
    with patch("sys.platform", "linux"):
        assert OllamaInstaller.detect_platform() == "linux"

def test_get_download_url():
    with patch("sys.platform", "win32"):
        url = OllamaInstaller.get_download_url()
        assert "OllamaSetup.exe" in url

@patch("src.core.ollama_installer.urllib.request.urlopen")
def test_download(mock_urlopen, tmp_path):
    mock_resp = MagicMock()
    mock_resp.headers.get.return_value = "100"
    mock_resp.read.side_effect = [b"chunk1", b"chunk2", b""]
    mock_urlopen.return_value.__enter__.return_value = mock_resp
    
    dest = tmp_path / "installer.exe"
    
    progress_calls = []
    def on_progress(pct, msg):
        progress_calls.append((pct, msg))
        
    OllamaInstaller.download(dest, progress_cb=on_progress)
    
    assert dest.exists()
    content = dest.read_bytes()
    assert content == b"chunk1chunk2"
    assert len(progress_calls) > 0
    assert progress_calls[-1][0] == 100 # Concluído

@patch("src.core.ollama_installer.subprocess.run")
def test_install_windows(mock_run):
    with patch.object(OllamaInstaller, "detect_platform", return_value="windows"):
        success = OllamaInstaller.install(Path("installer.exe"))
        assert success is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "installer.exe" in args[0]
        assert "/SILENT" in args

@patch("src.core.ollama_installer.subprocess.run")
def test_verify_success_cli(mock_run):
    # Simula timeout ou erro no urllib e fallback pro subprocess
    with patch("src.core.ollama_installer.urllib.request.urlopen", side_effect=Exception):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        assert OllamaInstaller.verify() is True
