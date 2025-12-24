import yt_dlp
import os

def download_audio_as_mp3(video_url, output_path="./downloads"):
    """
    Downloads the best available audio stream from a YouTube video and converts it to MP3.

    Args:
        video_url (str): The full URL of the YouTube video.
        output_path (str): The directory where the MP3 file will be saved. Defaults to './downloads'.
    """

    # Create the output directory if it doesn't exist
    os.makedirs(output_path, exist_ok=True)

    # Configure the download options for yt-dlp
    ydl_opts = {
        'format': 'bestaudio/best',  # Get the best available audio
        'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),  # Save files with the video title
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',  # Post-processor to extract audio
            'preferredcodec': 'mp3',      # Convert to MP3
            'preferredquality': '192',    # Target bitrate (192kbps)
        }],
        # Progress hooks to show status in console
        'progress_hooks': [lambda d: print(f"[Status] {d.get('_percent_str', 'N/A').strip()} downloaded")
                           if d['status'] == 'downloading' else None],
    }

    try:
        print(f"\nStarting download...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info first to show the title
            info = ydl.extract_info(video_url, download=False)
            print(f"Video: {info.get('title', 'Unknown Title')}")

            # Perform the download and conversion
            ydl.download([video_url])
        print(f"\n✓ Download and conversion complete! File saved to '{output_path}'")

    except Exception as e:
        print(f"\n✗ An error occurred: {e}")

if __name__ == "__main__":
    # Get user input for the YouTube URL
    url = input("Enter the YouTube video URL: ").strip()

    # Optional: Let the user specify a custom download folder
    custom_path = input("Enter download folder (press Enter for default './downloads'): ").strip()
    output_path = custom_path if custom_path else "./downloads"

    # Start the download process
    download_audio_as_mp3(url, output_path)