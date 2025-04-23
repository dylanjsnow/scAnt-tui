from nicegui import ui

def init():
    # Configure the NiceGUI application
    ui.title = "ScAnt Control Interface"
    # app.config.favicon = "favicon.ico"

    # Set up Tailwind CSS defaults
    ui.query('body').classes('min-h-screen bg-gray-900')  # Dark background
    ui.query('.nicegui-content').classes('p-4')  # Add padding to content

    # Custom card styling
    card_style = 'bg-gray-800 rounded-lg shadow-lg p-4 hover:shadow-xl transition-shadow duration-200'
    button_style = 'bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded'
    label_style = 'text-gray-200 text-lg font-medium'

    # Set up color scheme
    ui.colors(
        primary='#3B82F6',    # Blue-500
        secondary='#10B981',  # Emerald-500
        accent='#8B5CF6',    # Violet-500
        positive='#34D399',  # Emerald-400
        negative='#EF4444',  # Red-500
        warning='#F59E0B',   # Amber-500
        info='#3B82F6'      # Blue-500
    )

    ui.dark_mode(True)
